"""
基于 Redis 的流队列实现。

本模块提供 Redis Streams 实现的流队列，
用于需要分布式队列支持的生产环境部署。
"""

from typing import List, Optional, AsyncGenerator
import asyncio
import logging
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from .base_queue_manager import BaseStreamQueue, EventMessage
from ..config import settings

logger = logging.getLogger(__name__)


class RedisStreamQueue(BaseStreamQueue):
    """
    基于 Redis Streams 的队列实现。

    此队列使用 Redis Streams（XADD、XREAD、XRANGE）来存储和
    分发消息。支持分布式部署，并在服务器重启后提供持久化。
    """

    redis: Redis
    _pool: ConnectionPool
    _initialized: bool

    def __init__(
        self,
        queue_id: str,
        ttl: int = 300,
    ):
        """
        初始化 Redis 流队列。

        Args:
            queue_id: 队列的唯一标识符
            ttl: 队列的生存时间（秒）
        """
        super().__init__(queue_id, ttl)

        # 创建连接池和客户端
        pool_kwargs = {
            "host": settings.redis_host,
            "port": settings.redis_port,
            "db": settings.redis_db,
            "max_connections": settings.redis_max_connections,
            "decode_responses": True,  # 自动解码响应为字符串
            "socket_timeout": 5,  # Socket 超时
            "socket_connect_timeout": 5,  # 连接超时
            "retry_on_timeout": True,  # 超时重试
            "health_check_interval": 30,  # 健康检查
        }
        if settings.redis_username:
            pool_kwargs["username"] = settings.redis_username
        if settings.redis_password:
            pool_kwargs["password"] = settings.redis_password

        self._pool = ConnectionPool(**pool_kwargs)
        self.redis = Redis(connection_pool=self._pool)

        self.stream_key = f"{settings.redis_key_pre}:queue:{queue_id}"
        self.cancel_key = f"{settings.redis_key_pre}:queue:{queue_id}:cancel"
        self._initialized = False

    async def _ensure_initialized(self) -> None:
        """确保 Redis 连接已初始化。"""
        if not self._initialized:
            try:
                await self.redis.ping()  # type: ignore[misc]
                self._initialized = True
                logger.debug(f"Redis 连接已建立，队列 ID: {self.queue_id}")
            except (RedisError, RedisConnectionError) as e:
                logger.error(f"Redis 连接失败: {e}")
                raise ConnectionError(f"无法连接到 Redis: {e}") from e

    async def push(self, message: EventMessage) -> None:
        """
        将消息推送到 Redis 流。

        消息被序列化为 JSON 并使用 XADD 添加到流中。
        在流键上设置 TTL 以自动清理。

        Args:
            message: 要推送的事件消息

        Raises:
            ConnectionError: 当 Redis 连接失败时
            RedisError: 当 Redis 操作失败时
        """
        await self._ensure_initialized()

        try:
            # 序列化消息为 JSON
            message_data = message.model_dump_json()

            # 添加到 Redis 流
            await self.redis.xadd(
                self.stream_key,
                {"data": message_data}
            )

            # 设置流的 TTL
            await self.redis.expire(self.stream_key, self.ttl)
        except RedisError as e:
            logger.error(f"推送消息到 Redis 流失败: {e}")
            raise

    async def get_all(self) -> List[EventMessage]:
        """
        获取 Redis 流中当前的所有消息。

        使用 XRANGE 从流中检索所有消息。

        Returns:
            队列中所有事件消息的列表。

        Raises:
            ConnectionError: 当 Redis 连接失败时
            RedisError: 当 Redis 操作失败时
        """
        await self._ensure_initialized()

        messages = []

        try:
            # 从流中读取所有消息
            stream_data = await self.redis.xrange(self.stream_key)

            for message_id, fields in stream_data:
                # decode_responses=True 时，fields 已经是字符串字典
                if "data" in fields:
                    message_json = fields["data"]
                    message = EventMessage.model_validate_json(message_json)
                    messages.append(message)
        except RedisError as e:
            logger.error(f"从 Redis 流读取消息失败: {e}")
            raise

        return messages

    async def on_data_receive(self) -> AsyncGenerator[EventMessage, None]:
        """
        监听并生成 Redis 流中的消息。

        这使用带阻塞的 XREAD 来高效等待新消息。
        当收到终止事件或被取消时终止。

        Yields:
            队列中的事件消息。
        """
        await self._ensure_initialized()

        # 从开始读取
        last_id = "0"
        retry_count = 0
        max_retries = 3

        while not self.cancel_event.is_set():
            try:
                # 检查队列是否被取消
                is_cancelled = await self.redis.get(self.cancel_key)
                if is_cancelled:
                    logger.info(f"队列 {self.queue_id} 已被取消")
                    break

                # 使用阻塞方式从流中读取
                # 阻塞 1 秒以允许检查 cancel_event
                stream_data = await self.redis.xread(
                    {self.stream_key: last_id},
                    block=1000,
                    count=10
                )

                # 重置重试计数
                retry_count = 0

                if not stream_data:
                    # 没有新消息，继续
                    continue

                # 处理消息
                for _stream_name, messages in stream_data:
                    for msg_id, fields in messages:
                        # decode_responses=True 时，fields 和 message_id 已经是字符串
                        if "data" in fields:
                            message_json = fields["data"]
                            message = EventMessage.model_validate_json(message_json)

                            yield message

                            # 更新 last_id 用于下次读取
                            last_id = msg_id

                            # 检查是否为终止事件
                            if message.event in ["__stream_end__", "__stream_error__", "__stream_cancel__"]:
                                logger.info(f"收到终止事件: {message.event}")
                                return

            except asyncio.CancelledError:
                # 任务被取消
                logger.info(f"队列 {self.queue_id} 的数据接收被取消")
                break
            except RedisError as e:
                retry_count += 1
                logger.error(f"从 Redis 流读取时出错 (重试 {retry_count}/{max_retries}): {e}")

                if retry_count >= max_retries:
                    logger.error(f"达到最大重试次数，停止读取队列 {self.queue_id}")
                    break

                # 等待后重试
                await asyncio.sleep(min(retry_count * 2, 10))
            except Exception as e:
                # 记录错误但继续
                logger.error(f"处理 Redis 流消息时出现意外错误: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def cancel(self) -> None:
        """
        取消队列并停止所有操作。

        这会在 Redis 中设置取消标志，并通知所有消费者停止。
        """
        if self.cancel_event.is_set():
            logger.debug(f"队列 {self.queue_id} 已经被取消")
            return

        self.cancel_event.set()

        try:
            await self._ensure_initialized()

            # 在 Redis 中设置取消标志
            await self.redis.set(self.cancel_key, "1", ex=60)

            # 推送取消事件到流
            cancel_message = EventMessage(
                event="__stream_cancel__",
                data={"reason": "Queue cancelled"}
            )
            await self.push(cancel_message)
            logger.info(f"队列 {self.queue_id} 已取消")
        except Exception as e:
            logger.error(f"取消队列 {self.queue_id} 时出错: {e}")

    async def copy_to_queue(
        self,
        to_id: str,
        ttl: Optional[int] = None
    ) -> "RedisStreamQueue":
        """
        将此队列的数据复制到新的 Redis 流。

        Args:
            to_id: 新队列的 ID
            ttl: 新队列的可选 TTL。如果为 None，则使用此队列的 TTL。

        Returns:
            包含复制数据的新 RedisStreamQueue 实例。

        Raises:
            ConnectionError: 当 Redis 连接失败时
            RedisError: 当 Redis 操作失败时
        """
        await self._ensure_initialized()

        try:
            # 创建新队列
            new_queue = RedisStreamQueue(
                to_id,
                ttl or self.ttl,
            )

            # 复制所有消息
            messages = await self.get_all()
            for message in messages:
                await new_queue.push(message)

            logger.info(f"已将 {len(messages)} 条消息从队列 {self.queue_id} 复制到 {to_id}")
            return new_queue
        except Exception as e:
            logger.error(f"复制队列失败: {e}")
            raise

    async def cleanup(self) -> None:
        """
        清理 Redis 资源。

        从 Redis 中删除流和取消键，并关闭连接。
        """
        try:
            if self._initialized:
                # 删除 Redis 中的流和取消键
                await self.redis.delete(self.stream_key, self.cancel_key)
                logger.debug(f"已清理队列 {self.queue_id} 的 Redis 键")

            # 关闭 Redis 连接
            if self.redis:
                await self.redis.aclose()
                logger.debug(f"已关闭队列 {self.queue_id} 的 Redis 连接")

            # 关闭连接池
            if self._pool:
                await self._pool.aclose()
                logger.debug(f"已关闭队列 {self.queue_id} 的 Redis 连接池")
        except Exception as e:
            logger.error(f"清理队列 {self.queue_id} 时出错: {e}")

    async def __aenter__(self):
        """异步上下文管理器入口。"""
        await self._ensure_initialized()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):  # noqa: ANN001
        """异步上下文管理器退出。"""
        await self.cleanup()
