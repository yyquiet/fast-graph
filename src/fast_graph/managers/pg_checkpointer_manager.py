"""Checkpointer 服务模块"""
from typing import Optional, TYPE_CHECKING

from psycopg_pool import AsyncConnectionPool
from psycopg.rows import dict_row
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

if TYPE_CHECKING:
    from psycopg import AsyncConnection
    from psycopg.rows import DictRow

from ..config import settings
from .base_checkpointer_manager import BaseCheckpointerManager


class PostgresCheckpointerManager(BaseCheckpointerManager):
    """
    PostgreSQL Checkpointer 管理器
    """

    def __init__(self):
        """初始化 Checkpointer 管理器"""
        self.psycopg_pool: Optional["AsyncConnectionPool[AsyncConnection[DictRow]]"] = None

    async def init(self) -> None:
        """初始化 psycopg 连接池并创建表结构"""
        if self.psycopg_pool is None:
            self.psycopg_pool = AsyncConnectionPool(
                conninfo=settings.postgre_database_url,
                max_size=settings.postgre_db_pool_size,
                kwargs={"autocommit": True, "row_factory": dict_row},
                open=False
            )
            await self.psycopg_pool.open()

            # 初始化 checkpointer 表结构
            checkpointer = AsyncPostgresSaver(self.psycopg_pool)  # type: ignore
            await checkpointer.setup()

    async def close(self) -> None:
        """关闭连接池"""
        if self.psycopg_pool is not None:
            await self.psycopg_pool.close()
            self.psycopg_pool = None

    def get_checkpointer(self) -> AsyncPostgresSaver:
        """
        获取 Checkpointer 实例

        每次调用都返回新的 AsyncPostgresSaver 实例,共享底层连接池。
        连接池会自动管理连接的借用和归还,支持分布式高并发场景。

        Returns:
            AsyncPostgresSaver 实例

        Raises:
            RuntimeError: 如果连接池未初始化
        """
        if self.psycopg_pool is None:
            raise RuntimeError("Psycopg pool not initialized. Call init() first.")
        return AsyncPostgresSaver(self.psycopg_pool)  # type: ignore
