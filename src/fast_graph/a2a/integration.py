"""
A2A 集成模块

提供将 A2A 路由集成到 FastAPI 应用的功能
使用查询参数方式支持多个 assistant
"""

import logging
from typing import Dict, Any

import httpx
from fastapi import FastAPI, Request, Query, Response, Path, Body
from fastapi.responses import JSONResponse

from a2a.server.apps.jsonrpc.fastapi_app import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks.task_store import TaskStore
from a2a.server.tasks import (
    BasePushNotificationSender,
    InMemoryPushNotificationConfigStore,
    InMemoryTaskStore,
    DatabaseTaskStore,
)
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
)
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

from ..config import settings
from .agent_executor import GraphAgentExecutor
from ..services import AssistantsService
from ..errors import ResourceNotFoundError


logger = logging.getLogger(__name__)


# 全局存储：assistant_id -> A2A application
_assistant_apps: Dict[str, A2AFastAPIApplication] = {}

# 全局 TaskStore 实例（所有 assistant 共享）
_task_store: TaskStore | None = None

def _build_task_store() -> TaskStore:
    if settings.postgre_database_url:
        # 获取 PostgreSQL 连接并创建 DatabaseTaskStore
        from ..managers.pg_connection import get_pg_connection
        pg_conn = get_pg_connection()
        return DatabaseTaskStore(
            engine=pg_conn.engine,
            create_table=settings.postgre_auto_create_tables,  # 自动创建表
            table_name='a2a_tasks'  # 使用独立的表名
        )
    else:
        return InMemoryTaskStore()

def _get_task_store() -> TaskStore:
    """获取全局 TaskStore 实例"""
    global _task_store
    if _task_store is None:
        _task_store = _build_task_store()
    return _task_store


def setup_a2a_routes(
    app: FastAPI,
    host: str = settings.server_host,
    port: int = settings.server_port,
    agent_card_url: str = AGENT_CARD_WELL_KNOWN_PATH,
) -> None:
    """
    将 A2A 路由集成到现有的 FastAPI 应用中

    使用查询参数方式支持多个 assistant：
    - {agent_card_url}?assistant_id=xxx (AgentCard 端点)
    - /a2a/assistant_id (JSON-RPC 端点)

    Args:
        app: FastAPI 应用实例
        host: 服务器主机地址
        port: 服务器端口
        agent_card_url: Agent card 的 URL 路径

    """
    # 获取所有 assistants
    assistants_service = AssistantsService()
    assistants: dict = assistants_service.assistants

    if not assistants:
        logger.warning("No assistants found in AssistantsService. A2A routes will not be added.")
        return

    logger.info(f"Setting up A2A routes for {len(assistants)} assistant(s)")

    # 为每个 assistant 创建 A2A application
    for assistant_id, assistant in assistants.items():
        _create_assistant_app(
            assistant_id=assistant_id,
            assistant_name=assistant.name or assistant_id,
            assistant_description=assistant.description or f"LangGraph agent: {assistant.name or assistant_id}",
            host=host,
            port=port,
        )

    # 添加共享的路由
    @app.get(agent_card_url)
    async def get_agent_card(
        assistant_id: str = Query(..., description="Assistant ID")
    ) -> Response:
        """获取指定 assistant 的 agent card"""
        if assistant_id not in _assistant_apps:
            raise ResourceNotFoundError(f"Assistant '{assistant_id}' not found")

        a2a_app = _assistant_apps[assistant_id]
        # 创建一个临时请求对象
        from starlette.requests import Request as StarletteRequest
        from starlette.datastructures import Headers

        scope = {
            "type": "http",
            "method": "GET",
            "headers": [],
            "query_string": b"",
            "path": agent_card_url,
        }
        temp_request = StarletteRequest(scope)

        return await a2a_app._handle_get_agent_card(temp_request)

    @app.post("/a2a/{assistant_id}")
    async def handle_jsonrpc(
        request: Request,
        data: Any = Body(...),
        assistant_id: str = Path(..., description="Assistant ID")
    ) -> Response:
        """处理 JSON-RPC 请求"""
        if assistant_id not in _assistant_apps:
            return JSONResponse(
                status_code=404,
                content={
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32001,
                        "message": f"Assistant '{assistant_id}' not found"
                    },
                    "id": None
                }
            )

        a2a_app = _assistant_apps[assistant_id]

        # 直接调用 A2A app 的请求处理方法
        return await a2a_app._handle_requests(request)

    logger.info(f"A2A routes added: {agent_card_url}?assistant_id=xxx and /a2a/assistant_id")


def _create_assistant_app(
    assistant_id: str,
    assistant_name: str,
    assistant_description: str,
    host: str,
    port: int,
) -> None:
    """
    为单个 assistant 创建 A2A application

    Args:
        assistant_id: Assistant ID
        assistant_name: Assistant 名称
        assistant_description: Assistant 描述
        host: 服务器主机地址
        port: 服务器端口
    """
    # 创建 Agent Card
    capabilities = AgentCapabilities(
        streaming=True,                    # 支持流式响应
        push_notifications=False,          # 暂不支持推送通知
        state_transition_history=False     # 暂不支持状态转换历史
    )
    skill = AgentSkill(
        id=f'{assistant_id}_execution',
        name=f'{assistant_name} Execution',
        description=f'Execute {assistant_name} workflow',
        tags=['langgraph', 'assistant'],
        examples=[],
        input_modes=['application/json', 'text/plain'],
        output_modes=['application/json', 'text/plain'],
    )
    agent_card = AgentCard(  # type: ignore
        name=assistant_name,
        description=assistant_description,
        url=f'http://{host}:{port}/a2a/{assistant_id}',
        version='1.0.0',
        default_input_modes=['application/json', 'text/plain'],
        default_output_modes=['application/json', 'text/plain'],
        capabilities=capabilities,
        skills=[skill],
    )

    # 创建 Request Handler（每个 assistant 使用独立的 handler）
    httpx_client = httpx.AsyncClient()
    push_config_store = InMemoryPushNotificationConfigStore() #TODO 使用分布式Store来支持push_notifications
    push_sender = BasePushNotificationSender(
        httpx_client=httpx_client,
        config_store=push_config_store
    )
    request_handler = DefaultRequestHandler(
        agent_executor=GraphAgentExecutor(assistant_id),
        task_store=_get_task_store(),
        push_config_store=push_config_store,
        push_sender=push_sender
    )

    # 创建 A2A FastAPI Application
    a2a_app = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler
    )

    # 存储到全局字典
    _assistant_apps[assistant_id] = a2a_app

    logger.info(f"A2A application created for assistant '{assistant_id}'")
