"""
StatelessRunsService 测试类
"""

import pytest

from src.fast_graph.services.stateless_runs_service import StatelessRunsService
from src.fast_graph.models import RunCreateStateless, Assistant
from src.fast_graph.graph.registry import register_graph, GRAPHS
from src.fast_graph.global_config import GlobalConfig
from src.fast_graph.managers import (
    MemoryThreadsManager,
    MemoryStreamQueue,
    StreamQueueManager,
    MemoryCheckpointerManager,
)
from src.fast_graph.errors import GraphNotFoundError
from graph_demo.graph import create_normal_graph


# 辅助函数：注册图到服务
async def register_test_graph(service: StatelessRunsService, graph_id: str, graph):
    """注册图到 GRAPHS 和 AssistantsService"""
    await register_graph(graph_id, graph)
    assistant = Assistant(
        assistant_id=graph_id,
        graph_id=graph_id,
        name=graph_id,
        description="Test graph"
    )
    service.assistants_service.assistants[graph_id] = assistant


# 辅助函数：清理图
def cleanup_test_graph(service: StatelessRunsService, graph_id: str):
    """清理图"""
    if graph_id in GRAPHS:
        del GRAPHS[graph_id]
    if graph_id in service.assistants_service.assistants:
        del service.assistants_service.assistants[graph_id]


@pytest.fixture
async def service() -> StatelessRunsService:
    """服务 fixture"""
    # 初始化全局配置（使用内存模式）
    if not GlobalConfig.is_initialized:
        GlobalConfig.global_threads_manager = MemoryThreadsManager()
        GlobalConfig.global_queue_manager = StreamQueueManager(MemoryStreamQueue)
        GlobalConfig.global_checkpointer_manager = MemoryCheckpointerManager()
        GlobalConfig.is_initialized = True
    return StatelessRunsService()


class TestStatelessRunsService:
    """StatelessRunsService 测试类"""

    @pytest.mark.asyncio
    async def test_initialization(self, service: StatelessRunsService):
        """测试服务初始化"""
        assert service is not None
        assert service.executor is not None
        assert service.assistants_service is not None

    @pytest.mark.asyncio
    async def test_graph_not_found(self, service: StatelessRunsService):
        """测试图不存在时抛出异常"""
        payload = RunCreateStateless(  # type: ignore
            assistant_id="non_existent",
            input={"content": "test"}
        )

        with pytest.raises(GraphNotFoundError):
            await service.create_stateless_run_stream(payload)

    @pytest.mark.asyncio
    async def test_create_stream_success(self, service: StatelessRunsService):
        """测试成功创建流"""
        graph = create_normal_graph()
        await register_test_graph(service, "test_success", graph)

        try:
            payload = RunCreateStateless(  # type: ignore
                assistant_id="test_success",
                input={"content": "test", "auto_accepted": True, "not_throw_error": True}
            )

            response = await service.create_stateless_run_stream(payload)

            from fastapi.responses import StreamingResponse
            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"
        finally:
            cleanup_test_graph(service, "test_success")

    @pytest.mark.asyncio
    async def test_stream_with_context(self, service: StatelessRunsService):
        """测试带 context 的流式输出"""
        graph = create_normal_graph()
        await register_test_graph(service, "test_context", graph)

        try:
            payload = RunCreateStateless(  # type: ignore
                assistant_id="test_context",
                input={"content": "test", "auto_accepted": True, "not_throw_error": True},
                context={"user_id": "123"}
            )

            response = await service.create_stateless_run_stream(payload)

            from fastapi.responses import StreamingResponse
            assert isinstance(response, StreamingResponse)
        finally:
            cleanup_test_graph(service, "test_context")

    @pytest.mark.asyncio
    async def test_multiple_concurrent_streams(self, service: StatelessRunsService):
        """测试多个并发流"""
        import asyncio

        graph = create_normal_graph()
        await register_test_graph(service, "test_concurrent", graph)

        try:
            async def create_stream(index: int):
                payload = RunCreateStateless(  # type: ignore
                    assistant_id="test_concurrent",
                    input={
                        "content": f"test_{index}",
                        "auto_accepted": True,
                        "not_throw_error": True
                    }
                )
                return await service.create_stateless_run_stream(payload)

            responses = await asyncio.gather(
                create_stream(1),
                create_stream(2),
                create_stream(3)
            )

            from fastapi.responses import StreamingResponse
            for response in responses:
                assert isinstance(response, StreamingResponse)
        finally:
            cleanup_test_graph(service, "test_concurrent")
