"""
内存流队列管理器

用于测试和开发环境的内存版本流队列。
"""

import asyncio
from typing import List, Optional, AsyncGenerator

from .base_queue_manager import BaseStreamQueue, EventMessage


class MemoryStreamQueue(BaseStreamQueue):
    """
    内存流队列

    将事件消息存储在内存中，适用于测试和开发环境。
    不需要外部 Redis 依赖。
    """

    def __init__(self, queue_id: str, ttl: int = 300):
        """
        初始化内存流队列

        Args:
            queue_id: 队列的唯一标识符
            ttl: 队列的生存时间（秒），对于内存队列此参数仅用于兼容性
        """
        super().__init__(queue_id, ttl)
        self._messages: List[EventMessage] = []
        self._lock = asyncio.Lock()

    async def push(self, message: EventMessage) -> None:
        """
        将消息推送到队列

        Args:
            message: 要推送的事件消息
        """
        async with self._lock:
            self._messages.append(message)

    async def get_all(self) -> List[EventMessage]:
        """
        获取队列中当前的所有消息

        Returns:
            队列中所有事件消息的列表
        """
        async with self._lock:
            return self._messages.copy()

    async def on_data_receive(self) -> AsyncGenerator[EventMessage, None]:
        """
        监听并生成队列中的消息

        这是一个异步生成器，在消息到达时生成消息。
        当收到终止事件（__stream_end__、__stream_error__、__stream_cancel__）
        或队列被取消时，它应该终止。

        Yields:
            队列中的事件消息
        """
        index = 0

        while not self.cancel_event.is_set():
            async with self._lock:
                # 如果有新消息，生成它们
                while index < len(self._messages):
                    message = self._messages[index]
                    index += 1
                    yield message

                    # 检查是否是终止事件
                    if message.event in ["__stream_end__", "__stream_error__", "__stream_cancel__"]:
                        return

            # 如果没有新消息，短暂等待
            await asyncio.sleep(0.01)

    async def cancel(self) -> None:
        """
        取消队列并停止所有操作

        这会通知所有消费者停止并清理资源。
        """
        if not self.cancel_event.is_set():
            self.cancel_event.set()

            # 推送取消消息
            cancel_message = EventMessage(
                event="__stream_cancel__",
                data={"message": "Queue cancelled"}
            )
            await self.push(cancel_message)

    async def copy_to_queue(
        self,
        to_id: str,
        ttl: Optional[int] = None
    ) -> "MemoryStreamQueue":
        """
        将此队列的数据复制到新队列

        Args:
            to_id: 新队列的 ID
            ttl: 新队列的可选 TTL。如果为 None，则使用此队列的 TTL。

        Returns:
            包含复制数据的新队列实例
        """
        new_queue = MemoryStreamQueue(to_id, ttl or self.ttl)

        async with self._lock:
            new_queue._messages = self._messages.copy()

        return new_queue

    async def cleanup(self) -> None:
        """
        清理队列资源

        这会删除队列数据并释放所有相关资源。
        实现是幂等的，多次调用不会出错。
        """
        async with self._lock:
            self._messages.clear()

        self.cancel_event.set()

    async def __aenter__(self):
        """异步上下文管理器入口"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器退出"""
        await self.cleanup()
        return False

    def count(self) -> int:
        """
        获取队列中的消息数量

        这是一个辅助方法，用于测试和调试。

        Returns:
            消息数量
        """
        return len(self._messages)

    def clear(self) -> None:
        """
        清除所有消息

        这是一个同步辅助方法，用于测试环境中快速清理数据。
        """
        self._messages.clear()
