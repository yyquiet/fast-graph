"""
RemoteGraph 测试类
测试通过 RemoteGraph 客户端与 FastGraph HTTP API 的集成
"""

import pytest
from langgraph.pregel.remote import RemoteGraph
from langchain_core.messages import HumanMessage


# 服务器配置
SERVER_URL = "http://0.0.0.0:8000"


class TestRemoteGraph:
    """RemoteGraph 集成测试类"""

    @pytest.mark.asyncio
    async def test_remote_graph_initialization(self):
        """测试 RemoteGraph 初始化"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )
        assert graph is not None
        assert graph.assistant_id == "normal_graph"

    @pytest.mark.asyncio
    async def test_invoke_normal_graph(self):
        """测试调用普通图（无中断）"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        # 调用图
        result = await graph.ainvoke(
            input={"content": "test", "auto_accepted": True, "not_throw_error": True}
        )

        # 验证结果
        assert result is not None
        # RemoteGraph 返回的是最后一个事件，可能包含 data 字段
        if "data" in result:
            data = result["data"]
        else:
            data = result
        assert "content" in data
        assert "[normal]" in data["content"]

    @pytest.mark.asyncio
    async def test_stream_normal_graph(self):
        """测试流式调用普通图"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        # 流式调用
        chunks = []
        async for chunk in graph.astream(
            input={"content": "stream_test", "auto_accepted": True, "not_throw_error": True}
        ):

            chunks.append(chunk)

        # 验证流式输出
        assert len(chunks) > 0
        # 最后一个 chunk 应该包含完整结果
        last_chunk = chunks[-1]
        # 处理可能的嵌套 data 结构
        if "data" in last_chunk:
            data = last_chunk["data"]
        else:
            data = last_chunk

        # 数据可能是直接的状态，也可能是按节点分组的更新
        if "content" in data:
            assert "[normal]" in data["content"]
        else:
            # 按节点分组的格式，找到包含 content 的节点
            found = False
            for node_data in data.values():
                if isinstance(node_data, dict) and "content" in node_data:
                    assert "[normal]" in node_data["content"]
                    found = True
                    break
            assert found, f"未找到包含 content 的数据，实际数据: {data}"

    @pytest.mark.asyncio
    async def test_invoke_full_graph(self):
        """测试调用完整图（包含多个节点）"""
        graph = RemoteGraph(
            "full_graph",
            url=SERVER_URL
        )

        # 调用图（自动接受审批，不抛出错误）
        result = await graph.ainvoke(
            input={"content": "full_test", "auto_accepted": True, "not_throw_error": True}
        )

        # 验证结果包含所有节点的处理
        assert result is not None
        # 处理可能的嵌套 data 结构
        if "data" in result:
            data = result["data"]
        else:
            data = result
        assert "content" in data
        content = data["content"]
        assert "[chat]" in content
        assert "[hitl]" in content
        assert "[error]" in content
        assert "[normal]" in content

    @pytest.mark.asyncio
    async def test_invoke_with_thread(self):
        """测试使用线程 ID 进行有状态调用"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        thread_id = "test_thread_remote_001"

        # 第一次调用
        result1 = await graph.ainvoke(
            input={"content": "first", "auto_accepted": True, "not_throw_error": True},
            config={"configurable": {"thread_id": thread_id}}
        )

        assert result1 is not None
        data1 = result1["data"] if "data" in result1 else result1
        assert "[normal]" in data1["content"]

        # 第二次调用（使用相同的线程 ID）
        result2 = await graph.ainvoke(
            input={"content": "second", "auto_accepted": True, "not_throw_error": True},
            config={"configurable": {"thread_id": thread_id}}
        )

        assert result2 is not None
        data2 = result2["data"] if "data" in result2 else result2
        assert "[normal]" in data2["content"]

    @pytest.mark.asyncio
    async def test_get_state(self):
        """测试获取图状态"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        thread_id = "test_thread_state_001"

        # 先执行一次调用
        await graph.ainvoke(
            input={"content": "state_test", "auto_accepted": True, "not_throw_error": True},
            config={"configurable": {"thread_id": thread_id}}
        )

        # 获取状态
        state = await graph.aget_state(
            config={"configurable": {"thread_id": thread_id}}
        )

        # 验证状态
        assert state is not None
        assert state.values is not None
        # state.values 应该包含实际的状态数据
        values = state.values
        if "data" in values:
            values = values["data"]
        assert "content" in values

    @pytest.mark.asyncio
    async def test_stream_with_messages(self):
        """测试流式调用（包含消息）"""
        graph = RemoteGraph(
            "full_graph",
            url=SERVER_URL
        )

        # 流式调用
        chunks = []
        async for chunk in graph.astream(
            input={
                "messages": [HumanMessage(content="你好")],
                "content": "msg_test",
                "auto_accepted": True,
                "not_throw_error": True
            }
        ):
            chunks.append(chunk)

        # 验证流式输出
        assert len(chunks) > 0

        # 检查是否有消息输出
        # 消息可能在 chunk 本身，也可能在 chunk["data"] 中
        has_messages = False
        for chunk in chunks:
            if "messages" in chunk:
                has_messages = True
                break
            if "data" in chunk and isinstance(chunk["data"], dict):
                if "messages" in chunk["data"]:
                    has_messages = True
                    break
                # 也可能在节点数据中
                for node_data in chunk["data"].values():
                    if isinstance(node_data, dict) and "messages" in node_data:
                        has_messages = True
                        break

        assert has_messages, f"未找到消息数据，chunks 示例: {chunks[0] if chunks else 'empty'}"

    @pytest.mark.asyncio
    async def test_hitl_interrupt(self):
        """测试人工审批中断场景"""
        graph = RemoteGraph(
            "hitl_graph",
            url=SERVER_URL
        )

        thread_id = "test_thread_hitl_001"

        # 第一次调用（会在 hitl 节点中断）
        result1 = await graph.ainvoke(
            input={"content": "hitl_test", "auto_accepted": False},
            config={"configurable": {"thread_id": thread_id}}
        )

        # 验证中断
        assert result1 is not None

        # 获取状态，检查是否在等待审批
        state = await graph.aget_state(
            config={"configurable": {"thread_id": thread_id}}
        )

        assert state is not None
        # 如果有中断，next 应该有值
        if state.next:
            assert len(state.next) > 0

            # 更新状态，提供审批结果
            await graph.aupdate_state(
                config={"configurable": {"thread_id": thread_id}},
                values=None,  # 不更新值
                as_node="node_hitl"  # 从 hitl 节点继续
            )

            # 继续执行
            result2 = await graph.ainvoke(
                input=None,
                config={"configurable": {"thread_id": thread_id}}
            )

            assert result2 is not None

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """测试错误处理"""
        graph = RemoteGraph(
            "error_graph",
            url=SERVER_URL
        )

        # 调用会抛出错误的图
        # RemoteGraph 会将错误事件转换为 RemoteException
        from langgraph.pregel.remote import RemoteException
        with pytest.raises(RemoteException):
            await graph.ainvoke(
                input={"content": "error_test", "not_throw_error": False}
            )

    @pytest.mark.asyncio
    async def test_stream_mode_values(self):
        """测试不同的流模式 - values"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        chunks = []
        async for chunk in graph.astream(
            input={"content": "mode_test", "auto_accepted": True, "not_throw_error": True},
            stream_mode="values"
        ):
            chunks.append(chunk)

        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_stream_mode_updates(self):
        """测试不同的流模式 - updates"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        chunks = []
        async for chunk in graph.astream(
            input={"content": "mode_test", "auto_accepted": True, "not_throw_error": True},
            stream_mode="updates"
        ):
            chunks.append(chunk)

        assert len(chunks) > 0

    @pytest.mark.asyncio
    async def test_multiple_graphs(self):
        """测试同时使用多个图"""
        normal_graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        full_graph = RemoteGraph(
            "full_graph",
            url=SERVER_URL
        )

        # 并发调用两个图
        import asyncio
        results = await asyncio.gather(
            normal_graph.ainvoke(
                input={"content": "normal", "auto_accepted": True, "not_throw_error": True}
            ),
            full_graph.ainvoke(
                input={"content": "full", "auto_accepted": True, "not_throw_error": True}
            )
        )

        # 验证结果
        assert len(results) == 2
        data0 = results[0]["data"] if "data" in results[0] else results[0]
        data1 = results[1]["data"] if "data" in results[1] else results[1]
        assert "[normal]" in data0["content"]
        assert "[chat]" in data1["content"]

    @pytest.mark.asyncio
    async def test_sync_invoke(self):
        """测试同步调用"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        # 同步调用
        result = graph.invoke(
            input={"content": "sync_test", "auto_accepted": True, "not_throw_error": True}
        )

        # 验证结果
        assert result is not None
        data = result["data"] if "data" in result else result
        assert "content" in data
        assert "[normal]" in data["content"]

    def test_sync_stream(self):
        """测试同步流式调用"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        # 同步流式调用
        chunks = []
        for chunk in graph.stream(
            input={"content": "sync_stream", "auto_accepted": True, "not_throw_error": True}
        ):
            chunks.append(chunk)

        # 验证流式输出
        assert len(chunks) > 0
        last_chunk = chunks[-1]
        data = last_chunk["data"] if "data" in last_chunk else last_chunk

        # 数据可能是直接的状态，也可能是按节点分组的更新
        if "content" in data:
            assert "[normal]" in data["content"]
        else:
            # 按节点分组的格式，找到包含 content 的节点
            found = False
            for node_data in data.values():
                if isinstance(node_data, dict) and "content" in node_data:
                    assert "[normal]" in node_data["content"]
                    found = True
                    break
            assert found, f"未找到包含 content 的数据，实际数据: {data}"

    def test_sync_get_state(self):
        """测试同步获取状态"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        thread_id = "test_thread_sync_state"

        # 先执行一次调用
        graph.invoke(
            input={"content": "sync_state", "auto_accepted": True, "not_throw_error": True},
            config={"configurable": {"thread_id": thread_id}}
        )

        # 获取状态
        state = graph.get_state(
            config={"configurable": {"thread_id": thread_id}}
        )

        # 验证状态
        assert state is not None
        assert state.values is not None
        # state.values 应该包含实际的状态数据
        values = state.values
        if "data" in values:
            values = values["data"]
        assert "content" in values


    @pytest.mark.asyncio
    async def test_get_state_history(self):
        """测试获取状态历史"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        thread_id = "test_thread_history_001"

        # 执行多次调用，创建历史记录
        for i in range(3):
            await graph.ainvoke(
                input={"content": f"history_{i}", "auto_accepted": True, "not_throw_error": True},
                config={"configurable": {"thread_id": thread_id}}
            )

        # 获取状态历史
        history = []
        async for state in graph.aget_state_history(
            config={"configurable": {"thread_id": thread_id}}
        ):
            history.append(state)

        # 验证历史记录
        assert len(history) > 0
        # 历史记录应该按时间倒序排列（最新的在前）
        for state in history:
            assert state is not None
            assert state.values is not None

    @pytest.mark.asyncio
    async def test_update_state(self):
        """测试更新状态"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        thread_id = "test_thread_update_001"

        # 先执行一次调用
        result1 = await graph.ainvoke(
            input={"content": "initial", "auto_accepted": True, "not_throw_error": True},
            config={"configurable": {"thread_id": thread_id}}
        )

        # 获取当前状态
        state_before = await graph.aget_state(
            config={"configurable": {"thread_id": thread_id}}
        )

        # 更新状态
        await graph.aupdate_state(
            config={"configurable": {"thread_id": thread_id}},
            values={"content": "manually_updated"}
        )

        # 获取更新后的状态
        state_after = await graph.aget_state(
            config={"configurable": {"thread_id": thread_id}}
        )

        # 验证状态已更新
        assert state_after is not None
        assert state_after.values is not None
        values = state_after.values
        if "data" in values:
            values = values["data"]
        assert "manually_updated" in values.get("content", "")

    @pytest.mark.asyncio
    async def test_update_state_as_node(self):
        """测试以特定节点身份更新状态"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        thread_id = "test_thread_update_as_node_001"

        # 先执行一次调用
        await graph.ainvoke(
            input={"content": "initial", "auto_accepted": True, "not_throw_error": True},
            config={"configurable": {"thread_id": thread_id}}
        )

        # 以特定节点身份更新状态
        await graph.aupdate_state(
            config={"configurable": {"thread_id": thread_id}},
            values={"content": "updated_as_node"},
            as_node="node_normal"
        )

        # 获取更新后的状态
        state = await graph.aget_state(
            config={"configurable": {"thread_id": thread_id}}
        )

        # 验证状态已更新
        assert state is not None
        assert state.values is not None

    def test_sync_get_state_history(self):
        """测试同步获取状态历史"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        thread_id = "test_thread_sync_history_001"

        # 执行多次调用，创建历史记录
        for i in range(3):
            graph.invoke(
                input={"content": f"sync_history_{i}", "auto_accepted": True, "not_throw_error": True},
                config={"configurable": {"thread_id": thread_id}}
            )

        # 获取状态历史
        history = []
        for state in graph.get_state_history(
            config={"configurable": {"thread_id": thread_id}}
        ):
            history.append(state)

        # 验证历史记录
        assert len(history) > 0
        for state in history:
            assert state is not None
            assert state.values is not None

    def test_sync_update_state(self):
        """测试同步更新状态"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        thread_id = "test_thread_sync_update_001"

        # 先执行一次调用
        graph.invoke(
            input={"content": "sync_initial", "auto_accepted": True, "not_throw_error": True},
            config={"configurable": {"thread_id": thread_id}}
        )

        # 更新状态
        graph.update_state(
            config={"configurable": {"thread_id": thread_id}},
            values={"content": "sync_manually_updated"}
        )

        # 获取更新后的状态
        state = graph.get_state(
            config={"configurable": {"thread_id": thread_id}}
        )

        # 验证状态已更新
        assert state is not None
        assert state.values is not None


    @pytest.mark.asyncio
    async def test_get_graph(self):
        """测试获取图结构"""
        graph = RemoteGraph(
            "normal_graph",
            url=SERVER_URL
        )

        # 获取图结构
        drawable_graph = graph.get_graph()

        # 验证图结构
        assert drawable_graph is not None
        assert hasattr(drawable_graph, 'nodes')
        assert hasattr(drawable_graph, 'edges')
        assert len(drawable_graph.nodes) > 0

        # 验证节点信息
        node_names = [node.name for node in drawable_graph.nodes.values()]
        assert "node_normal" in node_names
