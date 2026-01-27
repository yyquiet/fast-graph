"""
RedisStreamQueue 测试类
"""

import pytest
import asyncio
from typing import List, AsyncGenerator
from unittest.mock import patch

from src.fast_graph.managers.redis_queue_manager import RedisStreamQueue
from src.fast_graph.managers.base_queue_manager import EventMessage, StreamQueueManager


@pytest.fixture
async def queue_manager() -> AsyncGenerator[StreamQueueManager[RedisStreamQueue], None]:
    """
    队列管理器 fixture，确保测试后总是清理资源。
    """
    # 创建 StreamQueueManager 实例
    manager = StreamQueueManager(RedisStreamQueue)

    yield manager

    # 测试结束后清理所有队列（即使测试失败也会执行）
    for queue_id, queue in list(manager.queues.items()):
        try:
            await queue.cleanup()
        except Exception as e:
            # 忽略清理错误，避免影响测试结果
            print(f"清理队列 {queue_id} 时出错: {e}")


class TestRedisStreamQueue:
    """RedisStreamQueue 测试类"""

    @pytest.mark.asyncio
    async def test_initialization(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试队列初始化"""
        queue = queue_manager.create_queue("test_queue_1", ttl=60)

        assert queue.queue_id == "test_queue_1"
        assert queue.ttl == 60
        assert not queue._initialized

    @pytest.mark.asyncio
    async def test_ensure_initialized(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试连接初始化"""
        queue = queue_manager.create_queue("test_queue_2", ttl=60)

        assert not queue._initialized

        await queue._ensure_initialized()

        assert queue._initialized

    @pytest.mark.asyncio
    async def test_push_message(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试推送消息"""
        queue = queue_manager.create_queue("test_queue_3", ttl=60)

        message = EventMessage(
            event="test_event",
            data={"key": "value"}
        )

        await queue.push(message)

        # 验证消息已推送
        messages = await queue.get_all()
        assert len(messages) == 1
        assert messages[0].event == "test_event"
        assert messages[0].data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_push_multiple_messages(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试推送多条消息"""
        queue = queue_manager.create_queue("test_queue_4", ttl=60)

        messages_to_push = [
            EventMessage(event="event_1", data={"index": 1}),
            EventMessage(event="event_2", data={"index": 2}),
            EventMessage(event="event_3", data={"index": 3}),
        ]

        for msg in messages_to_push:
            await queue.push(msg)

        # 验证所有消息
        retrieved_messages = await queue.get_all()
        assert len(retrieved_messages) == 3

        for i, msg in enumerate(retrieved_messages):
            assert msg.event == f"event_{i+1}"
            assert msg.data == {"index": i+1}

    @pytest.mark.asyncio
    async def test_get_all_empty_queue(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试获取空队列的所有消息"""
        queue = queue_manager.create_queue("test_queue_5", ttl=60)

        messages = await queue.get_all()
        assert len(messages) == 0

    @pytest.mark.asyncio
    async def test_on_data_receive(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试接收数据流"""
        queue = queue_manager.create_queue("test_queue_6", ttl=60)

        # 预先推送一些消息
        test_messages = [
            EventMessage(event="event_1", data={"msg": "first"}),
            EventMessage(event="event_2", data={"msg": "second"}),
            EventMessage(event="__stream_end__", data={"msg": "end"}),
        ]

        for msg in test_messages:
            await queue.push(msg)

        # 接收消息
        received_messages: List[EventMessage] = []
        async for message in queue.on_data_receive():
            received_messages.append(message)

        # 验证接收到的消息
        assert len(received_messages) == 3
        assert received_messages[0].event == "event_1"
        assert received_messages[1].event == "event_2"
        assert received_messages[2].event == "__stream_end__"

    @pytest.mark.asyncio
    async def test_on_data_receive_with_cancel(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试取消数据接收"""
        queue = queue_manager.create_queue("test_queue_7", ttl=60)

        # 推送一些消息
        await queue.push(EventMessage(event="event_1", data={}))

        received_messages: List[EventMessage] = []

        async def receive_data():
            async for message in queue.on_data_receive():
                received_messages.append(message)

        # 启动接收任务
        receive_task = asyncio.create_task(receive_data())

        # 等待一小段时间
        await asyncio.sleep(0.1)

        # 取消队列
        await queue.cancel()

        # 等待接收任务完成
        await asyncio.wait_for(receive_task, timeout=2.0)

        # 验证收到了取消消息
        assert any(msg.event == "__stream_cancel__" for msg in received_messages)

    @pytest.mark.asyncio
    async def test_cancel(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试取消队列"""
        queue = queue_manager.create_queue("test_queue_8", ttl=60)

        assert not queue.cancel_event.is_set()

        await queue.cancel()

        assert queue.cancel_event.is_set()

        # 验证取消标志已设置
        await queue._ensure_initialized()
        cancel_flag = await queue.redis.get(queue.cancel_key)
        assert cancel_flag == "1"

    @pytest.mark.asyncio
    async def test_cancel_idempotent(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试重复取消是幂等的"""
        queue = queue_manager.create_queue("test_queue_9", ttl=60)

        await queue.cancel()
        await queue.cancel()  # 第二次取消应该不会出错

        assert queue.cancel_event.is_set()

    @pytest.mark.asyncio
    async def test_copy_to_queue(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试复制队列"""
        source_queue = queue_manager.create_queue("source_queue", ttl=60)

        # 推送消息到源队列
        messages = [
            EventMessage(event="event_1", data={"index": 1}),
            EventMessage(event="event_2", data={"index": 2}),
        ]

        for msg in messages:
            await source_queue.push(msg)

        # 复制到新队列
        target_queue = await source_queue.copy_to_queue("target_queue", ttl=120)
        # 注册到管理器以便清理
        queue_manager.queues["target_queue"] = target_queue

        # 验证新队列
        assert target_queue.queue_id == "target_queue"
        assert target_queue.ttl == 120

        # 验证消息已复制
        target_messages = await target_queue.get_all()
        assert len(target_messages) == 2
        assert target_messages[0].event == "event_1"
        assert target_messages[1].event == "event_2"

    @pytest.mark.asyncio
    async def test_copy_to_queue_with_default_ttl(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试使用默认 TTL 复制队列"""
        source_queue = queue_manager.create_queue("source_queue_2", ttl=90)

        await source_queue.push(EventMessage(event="test", data={}))

        # 不指定 TTL，应使用源队列的 TTL
        target_queue = await source_queue.copy_to_queue("target_queue_2")
        # 注册到管理器以便清理
        queue_manager.queues["target_queue_2"] = target_queue

        assert target_queue.ttl == 90

    @pytest.mark.asyncio
    async def test_cleanup(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试清理资源"""
        queue = queue_manager.create_queue("test_queue_10", ttl=60)

        # 推送一些数据
        await queue.push(EventMessage(event="test", data={}))

        # 验证数据存在
        await queue._ensure_initialized()
        exists = await queue.redis.exists(queue.stream_key)
        assert exists == 1

        # 清理会在 fixture 中自动执行

    @pytest.mark.asyncio
    async def test_context_manager(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试异步上下文管理器"""
        # 创建备份队列以防上下文管理器失败
        backup_queue = queue_manager.create_queue("test_queue_11_backup", ttl=60)

        async with RedisStreamQueue("test_queue_11", ttl=60) as queue:
            await queue.push(EventMessage(event="test", data={}))
            messages = await queue.get_all()
            assert len(messages) == 1

        # 退出上下文后，资源应该已清理

    @pytest.mark.asyncio
    async def test_message_with_metadata(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试带元数据的消息"""
        queue = queue_manager.create_queue("test_queue_12", ttl=60)

        message = EventMessage(
            event="complex_event",
            data={
                "nested": {
                    "key": "value",
                    "list": [1, 2, 3]
                },
                "string": "test",
                "number": 42
            }
        )

        await queue.push(message)

        retrieved = await queue.get_all()
        assert len(retrieved) == 1
        assert retrieved[0].event == "complex_event"
        assert retrieved[0].data["nested"]["key"] == "value"
        assert retrieved[0].data["nested"]["list"] == [1, 2, 3]
        assert retrieved[0].data["number"] == 42

    @pytest.mark.asyncio
    async def test_concurrent_push(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试并发推送消息"""
        queue = queue_manager.create_queue("test_queue_13", ttl=60)

        async def push_messages(start_index: int, count: int):
            for i in range(count):
                msg = EventMessage(
                    event=f"event_{start_index + i}",
                    data={"index": start_index + i}
                )
                await queue.push(msg)

        # 并发推送
        await asyncio.gather(
            push_messages(0, 10),
            push_messages(10, 10),
            push_messages(20, 10),
        )

        # 验证所有消息都已推送
        messages = await queue.get_all()
        assert len(messages) == 30

    @pytest.mark.asyncio
    async def test_stream_end_events(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试不同的流结束事件"""
        for end_event in ["__stream_end__", "__stream_error__", "__stream_cancel__"]:
            queue = queue_manager.create_queue(f"test_queue_{end_event}", ttl=60)

            await queue.push(EventMessage(event="normal_event", data={}))
            await queue.push(EventMessage(event=end_event, data={}))

            received_count = 0
            async for message in queue.on_data_receive():
                received_count += 1
                if message.event == end_event:
                    break

            assert received_count == 2

    @pytest.mark.asyncio
    async def test_ttl_expiration(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试 TTL 超时后队列自动过期"""
        queue = queue_manager.create_queue("test_queue_ttl", ttl=2)

        # 推送消息
        message = EventMessage(event="test_event", data={"key": "value"})
        await queue.push(message)

        # 验证消息存在
        await queue._ensure_initialized()
        exists_before = await queue.redis.exists(queue.stream_key)
        assert exists_before == 1

        # 验证可以读取消息
        messages = await queue.get_all()
        assert len(messages) == 1

        # 等待 TTL 超时（2秒 + 0.5秒缓冲）
        await asyncio.sleep(2.5)

        # 验证队列已过期
        exists_after = await queue.redis.exists(queue.stream_key)
        assert exists_after == 0

        # 验证无法读取消息
        messages_after = await queue.get_all()
        assert len(messages_after) == 0
        assert len(messages_after) == 0


class TestRedisStreamQueueErrorHandling:
    """Redis 队列错误处理测试"""

    @pytest.mark.asyncio
    async def test_connection_error_handling(self):
        """测试连接错误处理"""
        # 使用错误的 Redis 配置
        with patch("src.fast_graph.managers.redis_queue_manager.settings") as mock_settings:
            mock_settings.redis_host = "invalid_host"
            mock_settings.redis_port = 9999
            mock_settings.redis_db = 0
            mock_settings.redis_max_connections = 10
            mock_settings.redis_username = None
            mock_settings.redis_password = None
            mock_settings.redis_key_pre = "test"

            queue = RedisStreamQueue("error_queue", ttl=60)

            # 应该抛出连接错误
            with pytest.raises(ConnectionError):
                await queue._ensure_initialized()

    @pytest.mark.asyncio
    async def test_cleanup_with_uninitialized_queue(self, queue_manager: StreamQueueManager[RedisStreamQueue]):
        """测试清理未初始化的队列"""
        queue = queue_manager.create_queue("uninit_queue", ttl=60)

        # 清理未初始化的队列不应抛出异常
        # fixture 会自动清理
