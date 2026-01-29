"""
GraphExecutor 测试类
"""

import pytest

from typing import AsyncGenerator
from src.fast_graph.graph.executor import GraphExecutor
from src.fast_graph.managers import (
    MemoryThreadsManager,
    MemoryStreamQueue,
    MemoryCheckpointerManager,
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
from graph_demo.graph import (
    create_full_graph,
    create_hitl_graph,
    create_error_graph,
    create_normal_graph,
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
    return GraphExecutor(thread_manager)


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
        await executor._handle_event(event, queue)

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
        await executor._handle_event(event, queue)

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
        await executor._handle_event(event, queue)

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
        thread_interrupted = await executor._handle_event(event, queue)

        # 验证返回值表示检测到中断
        assert thread_interrupted is True

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

        await executor._finalize_execution("test_thread", False, queue)

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

        await executor._finalize_execution("test_thread", True, queue)

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
        thread_manager: MemoryThreadsManager,
        checkpointer_manager: MemoryCheckpointerManager
    ):
        """测试成功执行图流"""
        thread = await thread_manager.create(thread_id="test_thread")

        # 使用实际的普通图（不会抛异常，不会中断）
        graph = create_normal_graph()

        # 为图配置 checkpointer
        graph.checkpointer = checkpointer_manager.get_checkpointer()

        # 创建 payload
        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": True, "not_throw_error": True}
        )

        # 执行
        await executor.stream_graph(graph, payload, queue, "test_thread")

        # 验证推送了元数据、事件和结束事件
        messages = await queue.get_all()
        assert len(messages) >= 3
        assert messages[0].event == "metadata"
        assert messages[-1].event == "__stream_end__"
        assert messages[-1].data["status"] == "success"

    @pytest.mark.asyncio
    async def test_stream_graph_with_error(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager,
        checkpointer_manager: MemoryCheckpointerManager
    ):
        """测试执行图时发生错误"""
        thread = await thread_manager.create(thread_id="test_thread")

        # 使用实际的错误图（会抛出 RuntimeError）
        graph = create_error_graph()

        # 为图配置 checkpointer
        graph.checkpointer = checkpointer_manager.get_checkpointer()

        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "not_throw_error": False}  # 不抑制错误
        )

        # 执行应该抛出异常
        with pytest.raises(RuntimeError, match="throw_error"):
            await executor.stream_graph(graph, payload, queue, "test_thread")

        # 验证推送了错误事件
        messages = await queue.get_all()
        error_events = [msg for msg in messages if msg.event == "__stream_error__"]
        assert len(error_events) == 1
        assert "throw_error" in error_events[0].data["error"]

    @pytest.mark.asyncio
    async def test_stream_graph_with_context(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager,
        checkpointer_manager: MemoryCheckpointerManager
    ):
        """测试带 context 的图执行"""
        thread = await thread_manager.create(thread_id="test_thread")

        # 使用实际的普通图
        graph = create_normal_graph()

        # 为图配置 checkpointer
        graph.checkpointer = checkpointer_manager.get_checkpointer()

        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": True, "not_throw_error": True},
            context={"user_id": "123"}
        )

        await executor.stream_graph(graph, payload, queue, "test_thread")

        # 验证执行成功
        messages = await queue.get_all()
        assert len(messages) >= 2
        assert messages[-1].event == "__stream_end__"

    @pytest.mark.asyncio
    async def test_stream_graph_with_interrupt(
        self,
        executor: GraphExecutor,
        queue: MemoryStreamQueue,
        thread_manager: MemoryThreadsManager,
        checkpointer_manager: MemoryCheckpointerManager
    ):
        """测试带中断的图执行"""
        thread = await thread_manager.create(thread_id="test_thread")

        # 使用实际的 HITL 图（会中断等待人工审批）
        graph = create_hitl_graph()

        # 为图配置 checkpointer
        graph.checkpointer = checkpointer_manager.get_checkpointer()

        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": False}  # 不自动接受，会触发中断
        )

        await executor.stream_graph(graph, payload, queue, "test_thread")

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
        thread_manager: MemoryThreadsManager,
        checkpointer_manager: MemoryCheckpointerManager
    ):
        """测试带子图的图执行"""
        thread = await thread_manager.create(thread_id="test_thread")

        # 使用实际的完整图
        graph = create_full_graph()

        # 为图配置 checkpointer
        graph.checkpointer = checkpointer_manager.get_checkpointer()

        payload = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": True, "not_throw_error": True},
            stream_subgraphs=True
        )

        await executor.stream_graph(graph, payload, queue, "test_thread")

        # 验证执行成功
        messages = await queue.get_all()
        assert len(messages) >= 2
        assert messages[-1].event == "__stream_end__"


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
        await executor._handle_event(event, queue)

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

        interrupted1 = await executor._handle_event(event1, queue)
        interrupted2 = await executor._handle_event(event2, queue)

        # 验证两次都检测到中断
        assert interrupted1 is True
        assert interrupted2 is True

        # 验证两个事件都被推送
        messages = await queue.get_all()
        assert len(messages) == 2


class TestGraphExecutorResume:
    """GraphExecutor 恢复执行测试"""

    @pytest.mark.asyncio
    async def test_resume_after_interrupt(
        self,
        executor: GraphExecutor,
        thread_manager: MemoryThreadsManager,
        checkpointer_manager: MemoryCheckpointerManager
    ):
        """测试中断后恢复执行"""
        thread = await thread_manager.create(thread_id="test_thread_resume")

        # 第一步：执行图直到中断
        graph = create_hitl_graph()
        # 直接设置 checkpointer
        graph.checkpointer = checkpointer_manager.get_checkpointer()

        queue1 = MemoryStreamQueue("queue1")
        payload1 = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "start", "auto_accepted": False}  # 会触发中断
        )

        await executor.stream_graph(graph, payload1, queue1, "test_thread_resume")

        # 验证线程状态为中断
        thread_after_interrupt = await thread_manager.get("test_thread_resume")
        assert thread_after_interrupt.status == ThreadStatus.interrupted

        messages1 = await queue1.get_all()
        end_events1 = [msg for msg in messages1 if msg.event == "__stream_end__"]
        assert len(end_events1) == 1
        assert end_events1[0].data["status"] == "interrupted"

        # 第二步：使用 Command 恢复执行
        queue2 = MemoryStreamQueue("queue2")
        payload2 = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            command=Command(  # type: ignore
                resume="[APPROVED]"  # 提供审批结果
            )
        )

        await executor.stream_graph(graph, payload2, queue2, "test_thread_resume")

        # 验证线程状态恢复为 idle（执行完成）
        thread_after_resume = await thread_manager.get("test_thread_resume")
        assert thread_after_resume.status == ThreadStatus.idle

        messages2 = await queue2.get_all()
        end_events2 = [msg for msg in messages2 if msg.event == "__stream_end__"]
        assert len(end_events2) == 1
        assert end_events2[0].data["status"] == "success"

        # 验证内容包含审批结果
        value_events = [msg for msg in messages2 if msg.event == "values"]
        assert len(value_events) > 0
        # 最后一个 values 事件应该包含完整的执行结果
        final_state = value_events[-1].data
        assert "[APPROVED]" in final_state.get("content", "")

    @pytest.mark.asyncio
    async def test_resume_after_error_with_update(
        self,
        executor: GraphExecutor,
        thread_manager: MemoryThreadsManager,
        checkpointer_manager: MemoryCheckpointerManager
    ):
        """测试异常后使用 Command.update 修复状态并恢复执行"""
        thread = await thread_manager.create(thread_id="test_thread_error")

        # 第一步：执行会抛出异常的图
        graph = create_error_graph()
        # 直接设置 checkpointer
        graph.checkpointer = checkpointer_manager.get_checkpointer()

        queue1 = MemoryStreamQueue("queue1")
        payload1 = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "start", "not_throw_error": False}  # 会抛出异常
        )

        # 执行应该抛出异常
        with pytest.raises(RuntimeError, match="throw_error"):
            await executor.stream_graph(graph, payload1, queue1, "test_thread_error")

        # 验证线程状态为 error
        thread_after_error = await thread_manager.get("test_thread_error")
        assert thread_after_error.status == ThreadStatus.error

        # 第二步：使用 Command.update 修复状态并恢复
        queue2 = MemoryStreamQueue("queue2")
        payload2 = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            command=Command(  # type: ignore
                update={"not_throw_error": True}  # 修复状态，不再抛异常
            )
        )

        await executor.stream_graph(graph, payload2, queue2, "test_thread_error")

        # 验证线程状态恢复为 idle（执行完成）
        thread_after_fix = await thread_manager.get("test_thread_error")
        assert thread_after_fix.status == ThreadStatus.idle

        messages2 = await queue2.get_all()
        end_events2 = [msg for msg in messages2 if msg.event == "__stream_end__"]
        assert len(end_events2) == 1
        assert end_events2[0].data["status"] == "success"

    @pytest.mark.asyncio
    async def test_resume_full_graph_after_interrupt(
        self,
        executor: GraphExecutor,
        thread_manager: MemoryThreadsManager,
        checkpointer_manager: MemoryCheckpointerManager
    ):
        """测试完整图中断后恢复执行"""
        thread = await thread_manager.create(thread_id="test_thread_full")

        # 第一步：执行完整图直到中断
        graph = create_full_graph()
        # 直接设置 checkpointer
        graph.checkpointer = checkpointer_manager.get_checkpointer()

        queue1 = MemoryStreamQueue("queue1")
        payload1 = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={
                "content": "",
                "auto_accepted": False,  # 会在 hitl 节点中断
                "not_throw_error": True
            }
        )

        await executor.stream_graph(graph, payload1, queue1, "test_thread_full")

        # 验证线程状态为中断
        thread_after_interrupt = await thread_manager.get("test_thread_full")
        assert thread_after_interrupt.status == ThreadStatus.interrupted

        # 第二步：恢复执行，继续完成剩余节点
        queue2 = MemoryStreamQueue("queue2")
        payload2 = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            command=Command(  # type: ignore
                resume="[APPROVED]"
            )
        )

        await executor.stream_graph(graph, payload2, queue2, "test_thread_full")

        # 验证线程状态恢复为 idle
        thread_after_resume = await thread_manager.get("test_thread_full")
        assert thread_after_resume.status == ThreadStatus.idle

        messages2 = await queue2.get_all()
        end_events2 = [msg for msg in messages2 if msg.event == "__stream_end__"]
        assert len(end_events2) == 1
        assert end_events2[0].data["status"] == "success"

        # 验证完整流程都执行了（chat -> hitl -> error -> normal）
        value_events = [msg for msg in messages2 if msg.event == "values"]
        assert len(value_events) > 0
        final_state = value_events[-1].data
        final_content = final_state.get("content", "")

        # 应该包含所有节点的标记
        assert "[chat]" in final_content
        assert "[hitl]" in final_content
        assert "[error]" in final_content
        assert "[normal]" in final_content
        assert "[APPROVED]" in final_content

    @pytest.mark.asyncio
    async def test_resume_with_goto(
        self,
        executor: GraphExecutor,
        thread_manager: MemoryThreadsManager,
        checkpointer_manager: MemoryCheckpointerManager
    ):
        """测试使用 Command.goto 跳转到特定节点恢复执行"""
        thread = await thread_manager.create(thread_id="test_thread_goto")

        # 第一步：执行图直到中断
        graph = create_hitl_graph()
        # 直接设置 checkpointer
        graph.checkpointer = checkpointer_manager.get_checkpointer()

        queue1 = MemoryStreamQueue("queue1")
        payload1 = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "start", "auto_accepted": False}
        )

        await executor.stream_graph(graph, payload1, queue1, "test_thread_goto")

        # 验证中断
        thread_after_interrupt = await thread_manager.get("test_thread_goto")
        assert thread_after_interrupt.status == ThreadStatus.interrupted

        # 第二步：使用 goto 直接跳转到结束（跳过当前中断节点）
        queue2 = MemoryStreamQueue("queue2")
        payload2 = RunCreateStateful(  # type: ignore
            assistant_id="test_assistant",
            command=Command(  # type: ignore
                resume="[REJECTED]",
                goto="__end__"  # 直接跳转到结束
            )
        )

        await executor.stream_graph(graph, payload2, queue2, "test_thread_goto")

        # 验证执行完成
        thread_after_goto = await thread_manager.get("test_thread_goto")
        assert thread_after_goto.status == ThreadStatus.idle

        messages2 = await queue2.get_all()
        end_events2 = [msg for msg in messages2 if msg.event == "__stream_end__"]
        assert len(end_events2) == 1
        assert end_events2[0].data["status"] == "success"
