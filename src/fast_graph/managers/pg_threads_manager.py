import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import (
    Column,
    String,
    DateTime,
    Index,
    select,
    update,
    delete,
    and_,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

from ..config import settings
from .base_threads_manager import BaseThreadsManager
from ..models import Thread, ThreadStatus
from ..errors import ResourceExistsError, ResourceNotFoundError

Base = declarative_base()


class ThreadModel(Base):
    """线程表的 SQLAlchemy 模型"""
    __tablename__ = 'thread'

    thread_id = Column(String, primary_key=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, nullable=False)
    # 使用 metadata_ 避免与 SQLAlchemy 的 metadata 属性冲突
    metadata_ = Column('metadata', JSONB, nullable=False, default={})
    status = Column(String, nullable=False, default='idle')

    __table_args__ = (
        Index('thread_created_at_idx', 'created_at', postgresql_using='btree'),
        Index('thread_metadata_idx', 'metadata', postgresql_using='gin', postgresql_ops={'metadata': 'jsonb_path_ops'}),
        Index('thread_status_idx', 'status', 'created_at', postgresql_using='btree'),
    )


class PostgresThreadsManager(BaseThreadsManager):
    """
    使用 SQLAlchemy 实现的 PostgreSQL 线程管理器

    表结构
        CREATE TABLE IF NOT EXISTS public.thread (
            thread_id TEXT PRIMARY KEY,
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP NOT NULL,
            metadata JSONB NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'idle'
        );
        CREATE INDEX thread_created_at_idx ON public.thread USING btree (created_at DESC);
        CREATE INDEX thread_metadata_idx ON public.thread USING gin (metadata jsonb_path_ops);
        CREATE INDEX thread_status_idx ON public.thread USING btree (status, created_at DESC);
    """

    def __init__(self):
        """初始化 PostgreSQL 连接池"""
        # 从环境变量读取数据库连接 URL
        db_url = settings.postgre_database_url
        if not db_url:
            raise ValueError("POSTGRE_DATABASE_URL environment variable is required")

        # 转换为异步 URL
        if db_url.startswith('postgresql://'):
            db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
        elif not db_url.startswith('postgresql+asyncpg://'):
            raise ValueError("POSTGRE_DATABASE_URL must use postgresql:// or postgresql+asyncpg:// scheme")

        # 创建异步引擎和连接池
        self.engine = create_async_engine(
            db_url,
            pool_size=settings.postgre_db_pool_size,
            max_overflow=settings.postgre_db_max_overflow,
            pool_pre_ping=True,  # 使用前验证连接
            echo=settings.postgre_db_echo,
        )

        # 创建会话工厂
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )

    async def setup(self) -> None:
        """初始化数据库表"""
        async with self.engine.begin() as conn:
            # create_all 会自动检查表是否存在（checkfirst=True 是默认值）
            # 如果表已存在，会跳过创建，不会报错也不会影响数据
            await conn.run_sync(Base.metadata.create_all)

    @staticmethod
    def _to_thread(model: ThreadModel) -> Thread:
        """将 ThreadModel 转换为 Thread 对象"""
        # 手动映射，因为 metadata 字段在 ORM 中命名为 metadata_
        return Thread(
            thread_id=model.thread_id,  # type: ignore
            created_at=model.created_at,  # type: ignore
            updated_at=model.updated_at,  # type: ignore
            metadata=model.metadata_,  # type: ignore
            status=ThreadStatus(model.status),  # type: ignore
        )

    async def create(
        self,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        if_exists: Optional[str] = None
    ) -> Thread:
        """创建新线程，使用原子事务处理"""
        if thread_id is None:
            thread_id = str(uuid.uuid4())

        if metadata is None:
            metadata = {}

        if if_exists is None:
            if_exists = 'raise'

        now = datetime.now()

        async with self.async_session() as session:
            async with session.begin():
                # 检查线程是否存在
                result = await session.execute(
                    select(ThreadModel).where(ThreadModel.thread_id == thread_id)
                )
                existing = result.scalar_one_or_none()

                if existing:
                    if if_exists == 'raise':
                        raise ResourceExistsError(f"Thread {thread_id} already exists")
                    elif if_exists == 'do_nothing':
                        return self._to_thread(existing)
                    else:
                        # 默认 raise
                        raise ResourceExistsError(f"Thread {thread_id} already exists")

                # 创建新线程
                thread_model = ThreadModel(
                    thread_id=thread_id,
                    created_at=now,
                    updated_at=now,
                    metadata_=metadata,  # 使用 metadata_
                    status='idle',
                )
                session.add(thread_model)

        return Thread(
            thread_id=thread_id,
            created_at=now,
            updated_at=now,
            metadata=metadata,
            status=ThreadStatus.idle,
        )

    async def get(self, thread_id: str) -> Thread:
        """通过 ID 检索线程"""
        async with self.async_session() as session:
            result = await session.execute(
                select(ThreadModel).where(ThreadModel.thread_id == thread_id)
            )
            thread_model = result.scalar_one_or_none()

            if not thread_model:
                raise ResourceNotFoundError(f"Thread {thread_id} not found")

            return self._to_thread(thread_model)

    async def search(
        self,
        ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: Optional[ThreadStatus] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Thread]:
        """搜索线程，支持过滤和分页"""
        async with self.async_session() as session:
            query = select(ThreadModel)

            # 构建过滤条件
            filters = []
            if ids:
                filters.append(ThreadModel.thread_id.in_(ids))
            if status:
                filters.append(ThreadModel.status == status.value)
            if metadata:
                # 使用 JSONB 包含查询过滤元数据（注意使用 metadata_）
                for key, value in metadata.items():
                    filters.append(ThreadModel.metadata_[key].astext == str(value))

            if filters:
                query = query.where(and_(*filters))

            # 应用排序和分页
            query = query.order_by(ThreadModel.created_at.desc())
            query = query.limit(limit).offset(offset)

            result = await session.execute(query)
            thread_models = result.scalars().all()

            return [self._to_thread(tm) for tm in thread_models]

    async def update(
        self,
        thread_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """更新线程属性，使用原子事务"""
        async with self.async_session() as session:
            async with session.begin():
                # 检查线程是否存在
                result = await session.execute(
                    select(ThreadModel).where(ThreadModel.thread_id == thread_id)
                )
                thread_model = result.scalar_one_or_none()

                if not thread_model:
                    raise ResourceNotFoundError(f"Thread {thread_id} not found")

                # 准备更新值
                update_values = updates.copy()
                update_values['updated_at'] = datetime.now()

                # 如果存在 ThreadStatus 枚举，转换为字符串
                if 'status' in update_values and isinstance(update_values['status'], ThreadStatus):
                    update_values['status'] = update_values['status'].value

                # 执行更新
                await session.execute(
                    update(ThreadModel)
                    .where(ThreadModel.thread_id == thread_id)
                    .values(**update_values)
                )

    async def delete(self, thread_id: str) -> None:
        """删除线程，使用原子事务"""
        async with self.async_session() as session:
            async with session.begin():
                # 检查线程是否存在
                result = await session.execute(
                    select(ThreadModel).where(ThreadModel.thread_id == thread_id)
                )
                thread_model = result.scalar_one_or_none()

                if not thread_model:
                    raise ResourceNotFoundError(f"Thread {thread_id} not found")

                # 删除线程
                await session.execute(
                    delete(ThreadModel).where(ThreadModel.thread_id == thread_id)
                )
