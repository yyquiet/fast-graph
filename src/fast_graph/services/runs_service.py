"""
Runs Service

处理有状态运行的业务逻辑
"""
from typing import Optional, AsyncGenerator
import threading
import uuid
import asyncio
import logging

from fastapi.responses import StreamingResponse

from ..models import (
    RunCreateStateful,
    ThreadStatus,
    ThreadCreate,
)
from ..graph.executor import GraphExecutor
from ..graph.registry import get_graph
from ..global_config import GlobalConfig
from ..managers import EventMessage
from ..errors import GraphNotFoundError, ResourceNotFoundError, ValidationError
from .assistants_service import AssistantsService
from .threads_service import ThreadsService

logger = logging.getLogger(__name__)


class RunsService:
    """线程安全的单例 Service"""

    _instance: Optional['RunsService'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式：确保只有一个实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化 runs（只执行一次）"""
        self.executor = GraphExecutor(GlobalConfig.global_threads_manager)
        self.assistants_service = AssistantsService()
        self.threads_service = ThreadsService()

    async def create_run_stream(
        self,
        thread_id: str,
        run_data: RunCreateStateful
    ) -> StreamingResponse:
        """
        在现有线程中创建运行并流式输出结果

        Args:
            thread_id: 线程 ID
            run_data: 运行配置

        Returns:
            StreamingResponse: 流式输出的执行结果

        Raises:
            GraphNotFoundError: 当指定的 assistant_id 对应的图不存在时
            ResourceNotFoundError: 当线程不存在且 if_not_exists='reject' 时
            ValidationError: 当线程正在运行时（并发控制）
        """
        # 处理 if_not_exists 参数
        # 使用原子的"获取或创建"操作避免竞态条件
        if run_data.if_not_exists == "create":
            # 尝试创建线程，如果已存在则返回现有线程
            thread_create = ThreadCreate(
                thread_id=thread_id,
                metadata={},
                if_exists="do_nothing"  # 如果已存在，返回现有线程
            )
            thread = await self.threads_service.create_thread(thread_create)
        else:
            # reject - 必须已存在
            try:
                thread = await self.threads_service.get(thread_id)
            except ResourceNotFoundError:
                raise ResourceNotFoundError(f"Thread {thread_id} not found")

        # 并发控制：原子地尝试获取锁
        lock_acquired = await GlobalConfig.global_threads_manager.acquire_lock(thread_id)
        if not lock_acquired:
            raise ValidationError(
                f"Thread {thread_id} is currently busy. "
                "Only one run can execute at a time per thread."
            )

        # 获取图实例
        assistant = await self.assistants_service.get_by_id(run_data.assistant_id)
        if assistant is None:
            raise GraphNotFoundError(
                f"Graph not found for assistant_id: {run_data.assistant_id}"
            )
        graph = await get_graph(assistant.graph_id)
        if graph is None:
            raise GraphNotFoundError(
                f"Graph not found for assistant_id: {run_data.assistant_id}"
            )

        # 配置 checkpointer
        graph.checkpointer = GlobalConfig.global_checkpointer_manager.get_checkpointer()

        # 创建队列用于流式输出
        queue_id = f"run_{thread_id}_{uuid.uuid4()}"
        queue = GlobalConfig.global_queue_manager.create_queue(
            queue_id=queue_id,
            ttl=300  # 5 分钟 TTL
        )

        # 在后台任务中执行图
        async def execute_graph():
            """后台执行图并将结果推送到队列"""
            try:
                # 锁已经在外面获取了，直接执行图
                await self.executor.stream_graph(graph, run_data, queue, thread_id)

            except Exception as e:
                logger.error(f"执行图时发生错误: {e}", exc_info=True)
            finally:
                # 清理队列
                await asyncio.sleep(1)  # 等待客户端接收完所有消息
                await queue.cleanup()

        # 启动后台任务
        asyncio.create_task(execute_graph())

        # 返回流式响应
        async def event_stream() -> AsyncGenerator[str, None]:
            """生成 SSE 格式的事件流"""
            try:
                async for message in queue.on_data_receive():
                    # 格式化为 SSE 格式
                    event_data = f"event: {message.event}\n"
                    event_data += f"data: {message.model_dump_json()}\n\n"
                    yield event_data
            except Exception as e:
                logger.error(f"流式输出时发生错误: {e}", exc_info=True)

        return StreamingResponse(
            event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
            }
        )
