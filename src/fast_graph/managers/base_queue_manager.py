"""
消息队列系统的基础接口。

本模块定义了流队列和事件消息的抽象基类，
为不同的队列实现提供一致的接口。
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any, List, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio
import uuid


# 定义泛型类型变量
QueueT = TypeVar('QueueT', bound='BaseStreamQueue')


class EventMessage(BaseModel):
    """
    流队列中的事件消息。

    事件消息用于通过流式传输将图执行事件
    从执行器传递给客户端。
    """
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="事件消息的唯一标识符"
    )
    event: str = Field(
        ...,
        description="事件类型（例如：'values', 'updates', 'metadata', '__stream_end__'）"
    )
    data: Any = Field(
        ...,
        description="事件数据"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="事件创建时的 ISO 8601 时间戳"
    )


class BaseStreamQueue(ABC):
    """
    流队列的抽象基类。

    流队列管理图执行期间的事件消息流，
    支持推送、消费和取消操作。
    """

    def __init__(self, queue_id: str, ttl: int = 300):
        """
        初始化流队列。

        Args:
            queue_id: 队列的唯一标识符
            ttl: 队列的生存时间（秒）
        """
        self.queue_id = queue_id
        self.ttl = ttl
        self.cancel_event = asyncio.Event()

    @abstractmethod
    async def push(self, message: EventMessage) -> None:
        """
        将消息推送到队列。

        Args:
            message: 要推送的事件消息
        """
        pass

    @abstractmethod
    async def get_all(self) -> List[EventMessage]:
        """
        获取队列中当前的所有消息。

        Returns:
            队列中所有事件消息的列表。
        """
        pass

    @abstractmethod
    def on_data_receive(self) -> AsyncGenerator[EventMessage, None]:
        """
        监听并生成队列中的消息。

        这是一个异步生成器，在消息到达时生成消息。
        当收到终止事件（__stream_end__、__stream_error__、__stream_cancel__）
        或队列被取消时，它应该终止。

        Yields:
            队列中的事件消息。
        """
        pass

    @abstractmethod
    async def cancel(self) -> None:
        """
        取消队列并停止所有操作。

        这应该通知所有消费者停止并清理资源。
        """
        pass

    @abstractmethod
    async def copy_to_queue(
        self,
        to_id: str,
        ttl: Optional[int] = None
    ) -> "BaseStreamQueue":
        """
        将此队列的数据复制到新队列。

        Args:
            to_id: 新队列的 ID
            ttl: 新队列的可选 TTL。如果为 None，则使用此队列的 TTL。

        Returns:
            包含复制数据的新队列实例。
        """
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """
        清理队列资源。

        这应该删除队列数据并释放所有相关资源（如连接、文件句柄等）。
        实现应该是幂等的，多次调用不应该出错。
        """
        pass


class StreamQueueManager(Generic[QueueT]):
    """
    流队列管理器。

    队列管理器创建和跟踪队列实例，提供
    集中管理多个队列的方式。

    泛型参数:
        QueueT: 队列类型，必须是 BaseStreamQueue 的子类
    """

    def __init__(self, queue_class: type[QueueT]):
        """
        初始化队列管理器。

        Args:
            queue_class: 用于创建新队列的队列类
        """
        self.queue_class = queue_class
        self.queues: Dict[str, QueueT] = {}

    def create_queue(self, queue_id: str, ttl: int = 300) -> QueueT:
        """
        创建新队列。

        Args:
            queue_id: 队列的唯一标识符
            ttl: 队列的生存时间（秒）

        Returns:
            创建的队列实例。
        """
        queue = self.queue_class(queue_id, ttl)
        self.queues[queue_id] = queue
        return queue

    async def get_queue(self, queue_id: str) -> QueueT:
        """
        通过 ID 获取现有队列。

        Args:
            queue_id: 队列标识符

        Returns:
            队列实例。

        Raises:
            ValueError: 如果未找到队列。
        """
        if queue_id not in self.queues:
            raise ValueError(f"Queue {queue_id} not found")
        return self.queues[queue_id]

    async def cancel_queue(self, queue_id: str) -> None:
        """
        取消并移除队列。

        Args:
            queue_id: 队列标识符
        """
        if queue_id in self.queues:
            await self.queues[queue_id].cancel()
            del self.queues[queue_id]
