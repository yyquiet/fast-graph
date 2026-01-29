"""
Stateless Runs Service

处理无状态运行的业务逻辑
"""
from typing import Optional, AsyncGenerator
import threading
import uuid
import asyncio
import logging

from fastapi.responses import StreamingResponse

from ..models import RunCreateStateless
from ..graph.stateless_executor import StatelessGraphExecutor
from ..graph.registry import get_graph
from ..global_config import GlobalConfig
from ..errors import GraphNotFoundError
from .assistants_service import AssistantsService

logger = logging.getLogger(__name__)


class StatelessRunsService:
    """
    无状态运行服务（线程安全的单例）

    无状态运行不需要 thread，不保存状态，每次执行都是独立的
    """

    _instance: Optional['StatelessRunsService'] = None
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
        """初始化服务（只执行一次）"""
        self.executor = StatelessGraphExecutor()
        self.assistants_service = AssistantsService()

    async def create_stateless_run_stream(
        self,
        run_data: RunCreateStateless
    ) -> StreamingResponse:
        """
        创建无状态运行并流式输出结果

        Args:
            run_data: 运行配置

        Returns:
            StreamingResponse: 流式输出的执行结果

        Raises:
            GraphNotFoundError: 当指定的 assistant_id 对应的图不存在时
        """
        # 通过 assistant_id 获取图实例
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

        # 创建队列用于流式输出
        queue_id = f"stateless_run_{uuid.uuid4()}"
        queue = GlobalConfig.global_queue_manager.create_queue(
            queue_id=queue_id,
            ttl=300  # 5 分钟 TTL
        )

        # 在后台任务中执行图
        async def execute_graph():
            """后台执行图并将结果推送到队列"""
            try:
                await self.executor.stream_graph(graph, run_data, queue)
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
