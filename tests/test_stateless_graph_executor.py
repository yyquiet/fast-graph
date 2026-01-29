"""
StatelessGraphExecutor 测试类
"""

import pytest

from src.fast_graph.graph.stateless_executor import StatelessGraphExecutor
from src.fast_graph.managers import MemoryStreamQueue
from src.fast_graph.models import (
    RunCreateStateless,
    StreamMode,
    Config,
)
from graph_demo.graph import (
    create_normal_graph,
    create_error_graph,
    create_full_graph,
)


@pytest.fixture
async def executor() -> StatelessGraphExecutor:
    """执行器 fixture"""
    return StatelessGraphExecutor()


@pytest.fixture
async def queue() -> MemoryStreamQueue:
    """队列 fixture"""
    return MemoryStreamQueue("test_queue")


class TestStatelessGraphExecutor:
    """StatelessGraphExecutor 测试类"""

    @pytest.mark.asyncio
    async def test_initialization(self, executor: StatelessGraphExecutor):
        """测试执行器初始化"""
        assert executor is not None

    @pytest.mark.asyncio
    async def test_normalize_stream_mode_none(self, executor: StatelessGraphExecutor):
        """测试规范化 None 流模式"""
        result = executor._normalize_stream_mode(None)
        assert result == ["values"]

    @pytest.mark.asyncio
    async def test_normalize_stream_mode_single(self, executor: StatelessGraphExecutor):
        """测试规范化单个流模式"""
        result = executor._normalize_stream_mode(StreamMode.updates)
        assert result == ["updates"]

    @pytest.mark.asyncio
    async def test_normalize_stream_mode_list(self, executor: StatelessGraphExecutor):
        """测试规范化流模式列表"""
        result = executor._normalize_stream_mode([StreamMode.values, StreamMode.updates])
        assert result == ["values", "updates"]

    @pytest.mark.asyncio
    async def test_prepare_input_with_input(self, executor: StatelessGraphExecutor):
        """测试准备普通输入"""
        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"message": "hello"}
        )
        result = executor._prepare_input(payload)
        assert result == {"message": "hello"}

    @pytest.mark.asyncio
    async def test_prepare_input_with_empty_input(self, executor: StatelessGraphExecutor):
        """测试准备空输入"""
        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input=None
        )
        result = executor._prepare_input(payload)
        assert result == {}

    @pytest.mark.asyncio
    async def test_build_config_basic(self, executor: StatelessGraphExecutor):
        """测试构建基础配置"""
        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant"
        )
        config = executor._build_config(payload)

        assert "configurable" in config
        assert config["configurable"] == {}

    @pytest.mark.asyncio
    async def test_build_config_with_user_config(self, executor: StatelessGraphExecutor):
        """测试构建带用户配置的配置"""
        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            config=Config(  # type: ignore
                tags=["tag1", "tag2"],
                recursion_limit=100,
                configurable={"custom_key": "custom_value"}
            )
        )
        config = executor._build_config(payload)

        assert config["tags"] == ["tag1", "tag2"]
        assert config["recursion_limit"] == 100
        assert config["configurable"]["custom_key"] == "custom_value"

    @pytest.mark.asyncio
    async def test_handle_event_tuple_2(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试处理二元组事件"""
        event = ("updates", {"node": "data"})
        await executor._handle_event(event, queue)

        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "updates"
        assert messages[0].data == {"node": "data"}

    @pytest.mark.asyncio
    async def test_handle_event_tuple_3(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试处理三元组事件"""
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
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试处理单值事件"""
        event = {"simple": "data"}
        await executor._handle_event(event, queue)

        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "values"
        assert messages[0].data == {"simple": "data"}

    @pytest.mark.asyncio
    async def test_handle_event_interrupt(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试处理中断事件"""
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
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试成功完成执行"""
        await executor._finalize_execution(False, queue)

        # 验证推送了成功结束事件
        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "__stream_end__"
        assert messages[0].data["status"] == "success"

    @pytest.mark.asyncio
    async def test_finalize_execution_interrupted(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试中断完成执行"""
        await executor._finalize_execution(True, queue)

        # 验证推送了中断结束事件
        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "__stream_end__"
        assert messages[0].data["status"] == "interrupted"

    @pytest.mark.asyncio
    async def test_handle_error(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试错误处理"""
        error = ValueError("Test error")
        await executor._handle_error(error, queue)

        # 验证推送了错误事件
        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "error"
        assert messages[0].data["error"] == "Test error"
        assert messages[0].data["type"] == "ValueError"

    @pytest.mark.asyncio
    async def test_stream_graph_success(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试成功执行图流"""
        # 使用实际的普通图（不会抛异常，不会中断）
        graph = create_normal_graph()
        graph = graph.compile()

        # 创建 payload
        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": True, "not_throw_error": True}
        )

        # 执行
        await executor.stream_graph(graph, payload, queue)

        # 验证推送了元数据、事件和结束事件
        messages = await queue.get_all()
        assert len(messages) >= 3
        assert messages[0].event == "metadata"
        assert messages[-1].event == "__stream_end__"
        assert messages[-1].data["status"] == "success"

    @pytest.mark.asyncio
    async def test_stream_graph_with_error(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试执行图时发生错误"""
        # 使用实际的错误图（会抛出 RuntimeError）
        graph = create_error_graph()
        graph = graph.compile()

        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "not_throw_error": False}  # 不抑制错误
        )

        # 执行应该抛出异常
        with pytest.raises(RuntimeError, match="throw_error"):
            await executor.stream_graph(graph, payload, queue)

        # 验证推送了错误事件
        messages = await queue.get_all()
        error_events = [msg for msg in messages if msg.event == "error"]
        assert len(error_events) == 1
        assert "throw_error" in error_events[0].data["error"]

    @pytest.mark.asyncio
    async def test_stream_graph_with_context(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试带 context 的图执行"""
        # 使用实际的普通图
        graph = create_normal_graph()
        graph = graph.compile()

        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": True, "not_throw_error": True},
            context={"user_id": "123"}
        )

        await executor.stream_graph(graph, payload, queue)

        # 验证执行成功
        messages = await queue.get_all()
        assert len(messages) >= 2
        assert messages[-1].event == "__stream_end__"

    @pytest.mark.asyncio
    async def test_stream_graph_with_subgraphs(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试带子图的图执行"""
        # 使用实际的完整图
        graph = create_full_graph()
        graph = graph.compile()

        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": True, "not_throw_error": True},
            stream_subgraphs=True
        )

        await executor.stream_graph(graph, payload, queue)

        # 验证执行成功
        messages = await queue.get_all()
        assert len(messages) >= 2
        assert messages[-1].event == "__stream_end__"

    @pytest.mark.asyncio
    async def test_stream_graph_with_multiple_stream_modes(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试使用多个流模式执行图"""
        graph = create_normal_graph()
        graph = graph.compile()

        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": True, "not_throw_error": True},
            stream_mode=[StreamMode.values, StreamMode.updates]
        )

        await executor.stream_graph(graph, payload, queue)

        # 验证执行成功
        messages = await queue.get_all()
        assert len(messages) >= 2
        assert messages[-1].event == "__stream_end__"

        # 验证包含不同类型的事件
        event_types = {msg.event for msg in messages}
        # 应该包含 values 或 updates 类型的事件
        assert any(event_type in ["values", "updates"] for event_type in event_types)


class TestStatelessGraphExecutorEdgeCases:
    """StatelessGraphExecutor 边界情况测试"""

    @pytest.mark.asyncio
    async def test_handle_event_with_none_data(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试处理 None 数据的事件"""
        event = ("values", None)
        await executor._handle_event(event, queue)

        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].data is None

    @pytest.mark.asyncio
    async def test_build_config_with_recursion_limit_zero(
        self,
        executor: StatelessGraphExecutor
    ):
        """测试构建递归限制为 0 的配置"""
        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            config=Config(  # type: ignore
                recursion_limit=0
            )
        )
        config = executor._build_config(payload)

        assert config["recursion_limit"] == 0

    @pytest.mark.asyncio
    async def test_multiple_interrupts(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试多次中断事件"""
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

    @pytest.mark.asyncio
    async def test_stream_graph_with_empty_config(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试使用空配置执行图"""
        graph = create_normal_graph()
        graph = graph.compile()

        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": True, "not_throw_error": True},
            config=None
        )

        await executor.stream_graph(graph, payload, queue)

        # 验证执行成功
        messages = await queue.get_all()
        assert len(messages) >= 2
        assert messages[-1].event == "__stream_end__"

    @pytest.mark.asyncio
    async def test_stream_graph_with_tags(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试带标签的图执行"""
        graph = create_normal_graph()
        graph = graph.compile()

        payload = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "", "auto_accepted": True, "not_throw_error": True},
            config=Config(  # type: ignore
                tags=["test", "stateless"]
            )
        )

        await executor.stream_graph(graph, payload, queue)

        # 验证执行成功
        messages = await queue.get_all()
        assert len(messages) >= 2
        assert messages[-1].event == "__stream_end__"

    @pytest.mark.asyncio
    async def test_handle_event_with_empty_dict(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试处理空字典事件"""
        event = {}
        await executor._handle_event(event, queue)

        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "values"
        assert messages[0].data == {}

    @pytest.mark.asyncio
    async def test_handle_event_with_nested_namespace(
        self,
        executor: StatelessGraphExecutor,
        queue: MemoryStreamQueue
    ):
        """测试处理嵌套命名空间事件"""
        event = ("parent:child:grandchild", "values", {"nested": "data"})
        await executor._handle_event(event, queue)

        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "values"
        assert messages[0].data["namespace"] == "parent:child:grandchild"
        assert messages[0].data["data"] == {"nested": "data"}


class TestStatelessGraphExecutorStatelessBehavior:
    """StatelessGraphExecutor 无状态行为测试"""

    @pytest.mark.asyncio
    async def test_multiple_executions_are_independent(
        self,
        executor: StatelessGraphExecutor
    ):
        """测试多次执行是相互独立的"""
        graph = create_normal_graph()
        graph = graph.compile()

        # 第一次执行
        queue1 = MemoryStreamQueue("queue1")
        payload1 = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "first", "auto_accepted": True, "not_throw_error": True}
        )
        await executor.stream_graph(graph, payload1, queue1)

        # 第二次执行
        queue2 = MemoryStreamQueue("queue2")
        payload2 = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "second", "auto_accepted": True, "not_throw_error": True}
        )
        await executor.stream_graph(graph, payload2, queue2)

        # 验证两次执行都成功
        messages1 = await queue1.get_all()
        messages2 = await queue2.get_all()

        assert len(messages1) >= 2
        assert len(messages2) >= 2
        assert messages1[-1].event == "__stream_end__"
        assert messages2[-1].event == "__stream_end__"

        # 验证两次执行的结果是独立的
        # 第一次执行的内容应该包含 "first"
        value_events1 = [msg for msg in messages1 if msg.event == "values"]
        assert any("first" in str(event.data) for event in value_events1)

        # 第二次执行的内容应该包含 "second"
        value_events2 = [msg for msg in messages2 if msg.event == "values"]
        assert any("second" in str(event.data) for event in value_events2)

    @pytest.mark.asyncio
    async def test_no_state_persistence_between_runs(
        self,
        executor: StatelessGraphExecutor
    ):
        """测试运行之间不保存状态"""
        graph = create_normal_graph()
        graph = graph.compile()

        # 第一次执行
        queue1 = MemoryStreamQueue("queue1")
        payload1 = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "run1", "auto_accepted": True, "not_throw_error": True}
        )
        await executor.stream_graph(graph, payload1, queue1)

        # 第二次执行，使用不同的输入
        queue2 = MemoryStreamQueue("queue2")
        payload2 = RunCreateStateless(  # type: ignore
            assistant_id="test_assistant",
            input={"content": "run2", "auto_accepted": True, "not_throw_error": True}
        )
        await executor.stream_graph(graph, payload2, queue2)

        # 验证第二次执行不包含第一次执行的内容
        messages2 = await queue2.get_all()
        value_events2 = [msg for msg in messages2 if msg.event == "values"]

        # 第二次执行的结果不应该包含 "run1"
        for event in value_events2:
            content = event.data.get("content", "")
            # 只应该包含 "run2" 相关的内容，不应该有 "run1"
            if "run1" in content and "run2" not in content:
                pytest.fail("第二次执行包含了第一次执行的状态")

    @pytest.mark.asyncio
    async def test_concurrent_executions(
        self,
        executor: StatelessGraphExecutor
    ):
        """测试并发执行"""
        import asyncio

        graph = create_normal_graph()
        graph = graph.compile()

        # 创建多个并发执行任务
        async def run_graph(index: int):
            queue = MemoryStreamQueue(f"queue_{index}")
            payload = RunCreateStateless(  # type: ignore
                assistant_id="test_assistant",
                input={
                    "content": f"concurrent_{index}",
                    "auto_accepted": True,
                    "not_throw_error": True
                }
            )
            await executor.stream_graph(graph, payload, queue)
            return queue

        # 并发执行 3 个任务
        queues = await asyncio.gather(
            run_graph(1),
            run_graph(2),
            run_graph(3)
        )

        # 验证所有执行都成功
        for i, queue in enumerate(queues, 1):
            messages = await queue.get_all()
            assert len(messages) >= 2
            assert messages[-1].event == "__stream_end__"
            assert messages[-1].data["status"] == "success"

            # 验证每个执行都有自己的内容
            value_events = [msg for msg in messages if msg.event == "values"]
            assert any(f"concurrent_{i}" in str(event.data) for event in value_events)
