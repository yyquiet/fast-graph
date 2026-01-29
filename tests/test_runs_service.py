"""
RunsService 测试类
"""

import pytest

from src.fast_graph.services.runs_service import RunsService
from src.fast_graph.models import RunCreateStateful, Assistant, ThreadCreate, ThreadStatus
from src.fast_graph.graph.registry import register_graph, GRAPHS
from src.fast_graph.global_config import GlobalConfig
from src.fast_graph.managers import (
    MemoryThreadsManager,
    MemoryStreamQueue,
    StreamQueueManager,
    MemoryCheckpointerManager,
)
from src.fast_graph.errors import GraphNotFoundError, ResourceNotFoundError, ValidationError
from graph_demo.graph import create_normal_graph


# 辅助函数：注册图到服务
async def register_test_graph(service: RunsService, graph_id: str, graph):
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
def cleanup_test_graph(service: RunsService, graph_id: str):
    """清理图"""
    if graph_id in GRAPHS:
        del GRAPHS[graph_id]
    if graph_id in service.assistants_service.assistants:
        del service.assistants_service.assistants[graph_id]


@pytest.fixture
async def service() -> RunsService:
    """服务 fixture"""
    # 初始化全局配置（使用内存模式）
    if not GlobalConfig.is_initialized:
        GlobalConfig.global_threads_manager = MemoryThreadsManager()
        GlobalConfig.global_queue_manager = StreamQueueManager(MemoryStreamQueue)
        GlobalConfig.global_checkpointer_manager = MemoryCheckpointerManager()
        GlobalConfig.is_initialized = True
    return RunsService()


class TestRunsService:
    """RunsService 测试类"""

    @pytest.mark.asyncio
    async def test_initialization(self, service: RunsService):
        """测试服务初始化"""
        assert service is not None
        assert service.executor is not None
        assert service.assistants_service is not None
        assert service.threads_service is not None

    @pytest.mark.asyncio
    async def test_graph_not_found(self, service: RunsService):
        """测试图不存在时抛出异常"""
        # 创建线程
        thread_create = ThreadCreate(thread_id="test_thread_1")  # type: ignore
        await service.threads_service.create_thread(thread_create)

        payload = RunCreateStateful(  # type: ignore
            assistant_id="non_existent",
            input={"content": "test"}
        )

        with pytest.raises(GraphNotFoundError):
            await service.create_run_stream("test_thread_1", payload)

    @pytest.mark.asyncio
    async def test_thread_not_found_reject(self, service: RunsService):
        """测试线程不存在且 if_not_exists='reject' 时抛出异常"""
        graph = create_normal_graph()
        await register_test_graph(service, "test_graph_reject", graph)

        try:
            payload = RunCreateStateful(  # type: ignore
                assistant_id="test_graph_reject",
                input={"content": "test"},
                if_not_exists="reject"
            )

            with pytest.raises(ResourceNotFoundError):
                await service.create_run_stream("non_existent_thread", payload)
        finally:
            cleanup_test_graph(service, "test_graph_reject")

    @pytest.mark.asyncio
    async def test_thread_not_found_create(self, service: RunsService):
        """测试线程不存在且 if_not_exists='create' 时自动创建"""
        graph = create_normal_graph()
        await register_test_graph(service, "test_graph_create", graph)

        try:
            payload = RunCreateStateful(  # type: ignore
                assistant_id="test_graph_create",
                input={"content": "test", "auto_accepted": True, "not_throw_error": True},
                if_not_exists="create"
            )

            response = await service.create_run_stream("auto_created_thread", payload)

            from fastapi.responses import StreamingResponse
            assert isinstance(response, StreamingResponse)

            # 验证线程已创建
            thread = await service.threads_service.get("auto_created_thread")
            assert thread is not None
            assert thread.thread_id == "auto_created_thread"
        finally:
            cleanup_test_graph(service, "test_graph_create")

    @pytest.mark.asyncio
    async def test_create_stream_success(self, service: RunsService):
        """测试成功创建流"""
        # 创建线程
        thread_create = ThreadCreate(thread_id="test_thread_success")  # type: ignore
        await service.threads_service.create_thread(thread_create)

        graph = create_normal_graph()
        await register_test_graph(service, "test_graph_success", graph)

        try:
            payload = RunCreateStateful(  # type: ignore
                assistant_id="test_graph_success",
                input={"content": "test", "auto_accepted": True, "not_throw_error": True}
            )

            response = await service.create_run_stream("test_thread_success", payload)

            from fastapi.responses import StreamingResponse
            assert isinstance(response, StreamingResponse)
            assert response.media_type == "text/event-stream"
            assert response.headers["Cache-Control"] == "no-cache"
            assert response.headers["Connection"] == "keep-alive"
        finally:
            cleanup_test_graph(service, "test_graph_success")

    @pytest.mark.asyncio
    async def test_concurrent_run_rejection(self, service: RunsService):
        """测试并发控制：同一线程不能同时运行多个任务"""
        # 创建线程
        thread_create = ThreadCreate(thread_id="test_thread_concurrent")  # type: ignore
        await service.threads_service.create_thread(thread_create)

        graph = create_normal_graph()
        await register_test_graph(service, "test_graph_concurrent", graph)

        try:
            # 第一次获取锁应该成功
            lock1 = await GlobalConfig.global_threads_manager.acquire_lock("test_thread_concurrent")
            assert lock1 is True

            # 第二次获取锁应该失败（已经被锁定）
            lock2 = await GlobalConfig.global_threads_manager.acquire_lock("test_thread_concurrent")
            assert lock2 is False

            # 尝试创建运行应该失败
            payload = RunCreateStateful(  # type: ignore
                assistant_id="test_graph_concurrent",
                input={"content": "test"}
            )

            with pytest.raises(ValidationError, match="currently busy"):
                await service.create_run_stream("test_thread_concurrent", payload)
        finally:
            cleanup_test_graph(service, "test_graph_concurrent")
            # 恢复线程状态
            await GlobalConfig.global_threads_manager.update(
                "test_thread_concurrent",
                {"status": ThreadStatus.idle}
            )

    @pytest.mark.asyncio
    async def test_concurrent_lock_race_condition(self, service: RunsService):
        """测试并发锁的竞态条件"""
        import asyncio

        # 创建线程
        thread_create = ThreadCreate(thread_id="test_thread_race")  # type: ignore
        await service.threads_service.create_thread(thread_create)

        # 模拟多个并发请求尝试获取锁
        async def try_acquire():
            return await GlobalConfig.global_threads_manager.acquire_lock("test_thread_race")

        # 并发执行 5 次获取锁操作
        results = await asyncio.gather(
            try_acquire(),
            try_acquire(),
            try_acquire(),
            try_acquire(),
            try_acquire()
        )

        # 只有一个应该成功
        success_count = sum(1 for r in results if r is True)
        assert success_count == 1, f"Expected 1 success, got {success_count}"

        # 恢复线程状态
        await GlobalConfig.global_threads_manager.update(
            "test_thread_race",
            {"status": ThreadStatus.idle}
        )

    @pytest.mark.asyncio
    async def test_stream_with_context(self, service: RunsService):
        """测试带 context 的流式输出"""
        # 创建线程
        thread_create = ThreadCreate(thread_id="test_thread_context")  # type: ignore
        await service.threads_service.create_thread(thread_create)

        graph = create_normal_graph()
        await register_test_graph(service, "test_graph_context", graph)

        try:
            payload = RunCreateStateful(  # type: ignore
                assistant_id="test_graph_context",
                input={"content": "test", "auto_accepted": True, "not_throw_error": True},
                context={"user_id": "123"}
            )

            response = await service.create_run_stream("test_thread_context", payload)

            from fastapi.responses import StreamingResponse
            assert isinstance(response, StreamingResponse)
        finally:
            cleanup_test_graph(service, "test_graph_context")

    @pytest.mark.asyncio
    async def test_concurrent_thread_creation(self, service: RunsService):
        """测试并发创建线程的场景"""
        import asyncio

        graph = create_normal_graph()
        await register_test_graph(service, "test_graph_concurrent_create", graph)

        try:
            # 模拟多个请求同时尝试创建同一个线程
            async def create_run(index: int):
                payload = RunCreateStateful(  # type: ignore
                    assistant_id="test_graph_concurrent_create",
                    input={"content": f"test_{index}", "auto_accepted": True, "not_throw_error": True},
                    if_not_exists="create"
                )
                return await service.create_run_stream("concurrent_thread_new", payload)

            # 并发执行 3 个请求
            responses = await asyncio.gather(
                create_run(1),
                create_run(2),
                create_run(3),
                return_exceptions=True  # 捕获异常而不是抛出
            )

            # 验证结果
            from fastapi.responses import StreamingResponse
            success_count = sum(1 for r in responses if isinstance(r, StreamingResponse))
            error_count = sum(1 for r in responses if isinstance(r, Exception))

            # 只有一个应该成功（获取到锁），其他的应该因为并发控制失败
            assert success_count == 1, f"Expected 1 success, got {success_count}"
            assert error_count == 2, f"Expected 2 errors, got {error_count}"

            # 验证线程已创建
            thread = await service.threads_service.get("concurrent_thread_new")
            assert thread is not None
        finally:
            cleanup_test_graph(service, "test_graph_concurrent_create")
