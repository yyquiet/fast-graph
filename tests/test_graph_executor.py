"""
GraphExecutor 测试类
"""

import pytest
from unittest.mock import AsyncMock

from typing import AsyncGenerator
from src.fast_graph.graph.executor import GraphExecutor
from src.fast_graph.managers import (
    MemoryThreadsManager,
    MemoryStreamQueue,
    MemoryCheckpointerManager,
    EventMessage,
)
from src.fast_graph.models import (
    RunCreateStateful,
    ThreadStatus,
    StreamMode,
    Thread,
    Command,
    Send,
    CheckpointConfig,
    Config,
)


@pytest.fixture
async def thread_manager() -> AsyncGenerator[MemoryThreadsManager, None]:
    """线程管理器 fixture"""
    manager = MemoryThreadsManager()
    await manager.setup()
    yield manager
    # 清理
    manager.clear()


@pytest.fixture
async def checkpointer_manager() -> MemoryCheckpointerManager:
    """Checkpointer 管理器 fixture"""
    return MemoryCheckpointerManager()


@pytest.fixture
async def executor(
    thread_manager: MemoryThreadsManager,
    checkpointer_manager: MemoryCheckpointerManager
) -> GraphExecutor:
    """执行器 fixture"""
    return GraphExecutor(thread_manager, checkpointer_manager)


@pytest.fixture
async def queue() -> MemoryStreamQueue:
    """队列 fixture"""
    return MemoryStreamQueue("test_queue")


@pytest.fixture
async def test_thread(thread_manager: MemoryThreadsManager) -> Thread:
    """测试线程 fixture"""
    return await thread_manager.create(thread_id="test_thread_1")


class TestGraphExecutor:
    """GraphExecutor 测试类"""

    @pytest.mark.asyncio
    async def test_initialization(self, executor: GraphExecutor):
        """测试执行器初始化"""
        assert executor.thread_manager is not None
        assert executor.checkpointer_manager is not None

    @pytest.mark.asyncio
    async def test_normalize_stream_mode_none(self, executor: GraphExecutor):
        """测试规范化 None 流模式"""
        result = executor._normalize_stream_mode(None)
        assert result == ["values"]

    @pytest.mark.asyncio
    async def test_normalize_stream_mode_single(self, executor: GraphExecutor):
        """测试规范化单个流模式"""
        result = executor._normalize_stream_mode(StreamMode.updates)
        assert result == ["updates"]

    @pytest.mark.asyncio
    async def test_normalize_stream_mode_list(self, executor: GraphExecutor):
        """测试规范化流模式列表"""
        result = executor._normalize_stream_mode([StreamMode.values, StreamMode.updates])
        assert result == ["values", "updates"]

    @pytest.mark.asyncio
    async def test_prepare_input_with_input(self, executor: GraphExecutor):
        """测试准备普通输入"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"message": "hello"}
        )
        result = executor._prepare_input(payload)
        assert result == {"message": "hello"}

    @pytest.mark.asyncio
    async def test_prepare_input_with_empty_input(self, executor: GraphExecutor):
        """测试准备空输入"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input=None
        )
        result = executor._prepare_input(payload)
        assert result == {}

    @pytest.mark.asyncio
    async def test_prepare_input_with_command(self, executor: GraphExecutor):
        """测试准备 Command 输入"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            command=Command(  # type: ignore
                update={"key": "value"},
                resume="resume_data"
            )
        )
        result = executor._prepare_input(payload)

        # 验证返回的是 Command 对象
        from langgraph.types import Command as LangGraphCommand
        assert isinstance(result, LangGraphCommand)

    @pytest.mark.asyncio
    async def test_prepare_input_with_command_goto_string(self, executor: GraphExecutor):
        """测试准备带 goto 字符串的 Command"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            command=Command(  # type: ignore
                update={"key": "value"},
                goto="next_node"
            )
        )
        result = executor._prepare_input(payload)

        from langgraph.types import Command as LangGraphCommand
        assert isinstance(result, LangGraphCommand)

    @pytest.mark.asyncio
    async def test_prepare_input_with_command_goto_send(self, executor: GraphExecutor):
        """测试准备带 goto Send 对象的 Command"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            command=Command(  # type: ignore
                goto=Send(  # type: ignore
                node="target_node", input={"data": "test"})
            )
        )
        result = executor._prepare_input(payload)

        from langgraph.types import Command as LangGraphCommand
        assert isinstance(result, LangGraphCommand)

    @pytest.mark.asyncio
    async def test_build_config_basic(self, executor: GraphExecutor):
        """测试构建基础配置"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant")
        config = executor._build_config("thread_123", payload)

        assert config["configurable"]["thread_id"] == "thread_123"

    @pytest.mark.asyncio
    async def test_build_config_with_checkpoint(self, executor: GraphExecutor):
        """测试构建带 checkpoint 的配置"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            checkpoint=CheckpointConfig(  # type: ignore  # type: ignore
                checkpoint_id="checkpoint_123",
                checkpoint_ns="namespace_1"
            )
        )
        config = executor._build_config("thread_123", payload)

        assert config["configurable"]["checkpoint_id"] == "checkpoint_123"
        assert config["configurable"]["checkpoint_ns"] == "namespace_1"

    @pytest.mark.asyncio
    async def test_build_config_with_user_config(self, executor: GraphExecutor):
        """测试构建带用户配置的配置"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            config=Config(  # type: ignore
                tags=["tag1", "tag2"],
                recursion_limit=100,
                configurable={"custom_key": "custom_value"}
            )
        )
        config = executor._build_config("thread_123", payload)

        assert config["tags"] == ["tag1", "tag2"]
        assert config["recursion_limit"] == 100
        assert config["configurable"]["custom_key"] == "custom_value"

    @pytest.mark.asyncio
    async def test_handle_event_tuple_2(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试处理二元组事件"""
        await thread_manager.create(thread_id="test_thread")

        event = ("updates", {"node": "data"})
        await executor._handle_event(event, queue, "test_thread")

        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "updates"
        assert messages[0].data == {"node": "data"}

    @pytest.mark.asyncio
    async def test_handle_event_tuple_3(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试处理三元组事件"""
        await thread_manager.create(thread_id="test_thread")

        event = ("namespace_1", "values", {"state": "data"})
        await executor._handle_event(event, queue, "test_thread")

        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "values"
        assert messages[0].data["namespace"] == "namespace_1"
        assert messages[0].data["data"] == {"state": "data"}

    @pytest.mark.asyncio
    async def test_handle_event_single_value(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试处理单值事件"""
        await thread_manager.create(thread_id="test_thread")

        event = {"simple": "data"}
        await executor._handle_event(event, queue, "test_thread")

        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "values"
        assert messages[0].data == {"simple": "data"}

    @pytest.mark.asyncio
    async def test_handle_event_interrupt(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试处理中断事件"""
        thread = await thread_manager.create(thread_id="test_thread")

        # 发送中断事件
        event = ("updates", {"__interrupt__": [{"value": "interrupt_data"}]})
        await executor._handle_event(event, queue, "test_thread")

        # 验证线程状态已更新为中断
        updated_thread = await thread_manager.get("test_thread")
        assert updated_thread.status == ThreadStatus.interrupted

        # 验证事件已推送
        messages = await queue.get_all()
        assert len(messages) == 1

    @pytest.mark.asyncio
    async def test_finalize_execution_success(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试成功完成执行"""
        thread = await thread_manager.create(thread_id="test_thread")
        await thread_manager.update("test_thread", {"status": ThreadStatus.busy})

        await executor._finalize_execution("test_thread", queue)

        # 验证推送了成功结束事件
        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "__stream_end__"
        assert messages[0].data["status"] == "success"

        # 验证线程状态更新为 idle
        updated_thread = await thread_manager.get("test_thread")
        assert updated_thread.status == ThreadStatus.idle

    @pytest.mark.asyncio
    async def test_finalize_execution_interrupted(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试中断完成执行"""
        thread = await thread_manager.create(thread_id="test_thread")
        await thread_manager.update("test_thread", {"status": ThreadStatus.interrupted})

        await executor._finalize_execution("test_thread", queue)

        # 验证推送了中断结束事件
        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "__stream_end__"
        assert messages[0].data["status"] == "interrupted"

    @pytest.mark.asyncio
    async def test_handle_error(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试错误处理"""
        thread = await thread_manager.create(thread_id="test_thread")

        error = ValueError("Test error")
        await executor._handle_error(error, "test_thread", queue)

        # 验证推送了错误事件
        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "__stream_error__"
        assert messages[0].data["error"] == "Test error"
        assert messages[0].data["type"] == "ValueError"

        # 验证线程状态更新为 error
        updated_thread = await thread_manager.get("test_thread")
        assert updated_thread.status == ThreadStatus.error

    @pytest.mark.asyncio
    async def test_stream_graph_success(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试成功执行图流"""
        thread = await thread_manager.create(thread_id="test_thread")

        # 创建模拟图
        mock_graph = AsyncMock()

        # 模拟 astream 返回事件流
        async def mock_astream(*args, **kwargs):
            yield ("values", {"state": "step1"})
            yield ("values", {"state": "step2"})

        mock_graph.astream = mock_astream

        # 创建 payload
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"message": "hello"}
        )

        # 执行
        await executor.stream_graph(mock_graph, payload, queue, "test_thread")

        # 验证推送了元数据、事件和结束事件
        messages = await queue.get_all()
        assert len(messages) >= 3
        assert messages[0].event == "metadata"
        assert messages[-1].event == "__stream_end__"

    @pytest.mark.asyncio
    async def test_stream_graph_with_error(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试执行图时发生错误"""
        thread = await thread_manager.create(thread_id="test_thread")

        # 创建会抛出异常的模拟图
        mock_graph = AsyncMock()

        async def mock_astream_error(*args, **kwargs):
            yield ("values", {"state": "step1"})
            raise RuntimeError("Graph execution failed")

        mock_graph.astream = mock_astream_error

        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"message": "hello"}
        )

        # 执行应该抛出异常
        with pytest.raises(RuntimeError):
            await executor.stream_graph(mock_graph, payload, queue, "test_thread")

        # 验证推送了错误事件
        messages = await queue.get_all()
        error_events = [msg for msg in messages if msg.event == "__stream_error__"]
        assert len(error_events) == 1
        assert "Graph execution failed" in error_events[0].data["error"]

    @pytest.mark.asyncio
    async def test_stream_graph_with_context(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试带 context 的图执行"""
        thread = await thread_manager.create(thread_id="test_thread")

        mock_graph = AsyncMock()

        async def mock_astream(*args, **kwargs):
            # 验证 context 参数被传递
            assert "context" in kwargs
            assert kwargs["context"] == {"user_id": "123"}
            yield ("values", {"state": "done"})

        mock_graph.astream = mock_astream

        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"message": "hello"},
            context={"user_id": "123"}
        )

        await executor.stream_graph(mock_graph, payload, queue, "test_thread")

    @pytest.mark.asyncio
    async def test_stream_graph_with_interrupt(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试带中断的图执行"""
        thread = await thread_manager.create(thread_id="test_thread")

        mock_graph = AsyncMock()

        async def mock_astream(*args, **kwargs):
            yield ("values", {"state": "step1"})
            yield ("updates", {"__interrupt__": [{"value": "waiting"}]})

        mock_graph.astream = mock_astream

        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"message": "hello"}
        )

        await executor.stream_graph(mock_graph, payload, queue, "test_thread")

        # 验证线程状态为中断
        updated_thread = await thread_manager.get("test_thread")
        assert updated_thread.status == ThreadStatus.interrupted

        # 验证推送了中断结束事件
        messages = await queue.get_all()
        end_events = [msg for msg in messages if msg.event == "__stream_end__"]
        assert len(end_events) == 1
        assert end_events[0].data["status"] == "interrupted"

    @pytest.mark.asyncio
    async def test_stream_graph_with_subgraphs(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试带子图的图执行"""
        thread = await thread_manager.create(thread_id="test_thread")

        mock_graph = AsyncMock()

        async def mock_astream(*args, **kwargs):
            # 验证 subgraphs 参数
            assert kwargs.get("subgraphs") is True
            # 返回三元组格式（带 namespace）
            yield ("subgraph_1", "values", {"state": "sub_step"})
            yield ("values", {"state": "main_step"})

        mock_graph.astream = mock_astream

        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"message": "hello"},
            stream_subgraphs=True
        )

        await executor.stream_graph(mock_graph, payload, queue, "test_thread")

        # 验证处理了带 namespace 的事件
        messages = await queue.get_all()
        namespace_events = [
            msg for msg in messages
            if isinstance(msg.data, dict) and "namespace" in msg.data
        ]
        assert len(namespace_events) >= 1


class TestGraphExecutorEdgeCases:
    """GraphExecutor 边界情况测试"""

    @pytest.mark.asyncio
    async def test_handle_event_with_none_data(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试处理 None 数据的事件"""
        await thread_manager.create(thread_id="test_thread")

        event = ("values", None)
        await executor._handle_event(event, queue, "test_thread")

        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].data is None

    @pytest.mark.asyncio
    async def test_prepare_input_with_command_goto_list(self, executor: GraphExecutor):
        """测试准备带 goto 列表的 Command"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            command=Command(  # type: ignore
                goto=["node1", "node2"]
            )
        )
        result = executor._prepare_input(payload)

        from langgraph.types import Command as LangGraphCommand
        assert isinstance(result, LangGraphCommand)

    @pytest.mark.asyncio
    async def test_prepare_input_with_command_goto_send_list(self, executor: GraphExecutor):
        """测试准备带 goto Send 列表的 Command"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            command=Command(  # type: ignore
                goto=[
                    Send(  # type: ignore
                node="node1", input={"data": "1"}),
                    Send(  # type: ignore
                node="node2", input={"data": "2"})
                ]
            )
        )
        result = executor._prepare_input(payload)

        from langgraph.types import Command as LangGraphCommand
        assert isinstance(result, LangGraphCommand)

    @pytest.mark.asyncio
    async def test_build_config_with_recursion_limit_zero(self, executor: GraphExecutor):
        """测试构建递归限制为 0 的配置"""
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            config=Config(  # type: ignore
                recursion_limit=0)
        )
        config = executor._build_config("thread_123", payload)

        assert config["recursion_limit"] == 0

    @pytest.mark.asyncio
    async def test_multiple_interrupts(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager
    ):
        """测试多次中断事件"""
        thread = await thread_manager.create(thread_id="test_thread")

        # 发送多个中断事件
        event1 = ("updates", {"__interrupt__": [{"value": "interrupt1"}]})
        event2 = ("updates", {"__interrupt__": [{"value": "interrupt2"}]})

        await executor._handle_event(event1, queue, "test_thread")
        await executor._handle_event(event2, queue, "test_thread")

        # 验证状态仍然是中断
        updated_thread = await thread_manager.get("test_thread")
        assert updated_thread.status == ThreadStatus.interrupted

        # 验证两个事件都被推送
        messages = await queue.get_all()
        assert len(messages) == 2
