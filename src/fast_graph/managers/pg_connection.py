"""PostgreSQL 数据库连接管理模块"""
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base

from ..config import settings

# 全局 Base 对象,用于所有 PostgreSQL 模型
Base = declarative_base()


class PostgresConnection:
    """PostgreSQL 数据库连接管理器 - 使用 psycopg 驱动"""

    def __init__(self):
        """初始化 PostgreSQL 连接"""
        # 从配置获取数据库 URL
        db_url = settings.postgre_database_url
        if not db_url:
            raise ValueError("POSTGRE_DATABASE_URL environment variable is required")

        # 转换为 SQLAlchemy psycopg 异步 URL
        sqlalchemy_url = db_url
        if sqlalchemy_url.startswith('postgresql://'):
            sqlalchemy_url = sqlalchemy_url.replace('postgresql://', 'postgresql+psycopg_async://', 1)
        elif not sqlalchemy_url.startswith('postgresql+psycopg'):
            raise ValueError("POSTGRE_DATABASE_URL must use postgresql:// or postgresql+psycopg_async:// scheme")

        # 创建 SQLAlchemy 异步引擎 (使用 psycopg)
        self.engine: AsyncEngine = create_async_engine(
            sqlalchemy_url,
            pool_size=settings.postgre_db_pool_size,
            max_overflow=settings.postgre_db_max_overflow,
            pool_pre_ping=True,  # 使用前验证连接
            echo=settings.postgre_db_echo,
        )

        # 创建 SQLAlchemy 会话工厂
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def init_tables(self) -> None:
        """初始化数据库表结构"""
        async with self.engine.begin() as conn:
            # create_all 会自动检查表是否存在
            # 如果表已存在,会跳过创建,不会报错也不会影响数据
            if settings.postgre_auto_create_tables:
                await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """关闭数据库连接"""
        await self.engine.dispose()


# 全局单例连接实例
_pg_connection: Optional[PostgresConnection] = None


def get_pg_connection() -> PostgresConnection:
    """获取全局 PostgreSQL 连接实例"""
    global _pg_connection
    if _pg_connection is None:
        _pg_connection = PostgresConnection()
    return _pg_connection


async def init_pg_connection() -> PostgresConnection:
    """
    初始化全局 PostgreSQL 连接

    Returns:
        PostgresConnection 实例
    """
    global _pg_connection
    _pg_connection = PostgresConnection()
    await _pg_connection.init_tables()
    return _pg_connection


async def close_pg_connection() -> None:
    """关闭全局 PostgreSQL 连接"""
    global _pg_connection
    if _pg_connection is not None:
        await _pg_connection.close()
        _pg_connection = None
