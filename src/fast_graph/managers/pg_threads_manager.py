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

from .base_threads_manager import BaseThreadsManager
from .pg_connection import Base, get_pg_connection
from ..models import Thread, ThreadStatus
from ..errors import ResourceExistsError, ResourceNotFoundError


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
        """初始化 PostgreSQL 线程管理器"""
        # 获取全局 PostgreSQL 连接
        self._pg_conn = get_pg_connection()
        self.async_session = self._pg_conn.async_session

    async def setup(self) -> None:
        """初始化数据库表"""
        await self._pg_conn.init_tables()

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
                if if_exists == 'do_nothing':
                    # 使用 INSERT ... ON CONFLICT DO NOTHING 实现原子的"获取或创建"
                    # 这比先 SELECT 再 INSERT 更安全
                    from sqlalchemy.dialects.postgresql import insert

                    stmt = insert(ThreadModel).values(
                        thread_id=thread_id,
                        created_at=now,
                        updated_at=now,
                        metadata_=metadata,
                        status='idle',
                    ).on_conflict_do_nothing(index_elements=['thread_id'])

                    await session.execute(stmt)

                    # 获取线程（可能是刚创建的，也可能是已存在的）
                    result = await session.execute(
                        select(ThreadModel).where(ThreadModel.thread_id == thread_id)
                    )
                    thread_model = result.scalar_one()
                    return self._to_thread(thread_model)
                else:
                    # if_exists == 'raise' 或其他值
                    # 检查线程是否存在
                    result = await session.execute(
                        select(ThreadModel).where(ThreadModel.thread_id == thread_id)
                    )
                    existing = result.scalar_one_or_none()

                    if existing:
                        raise ResourceExistsError(f"Thread {thread_id} already exists")

                    # 创建新线程
                    thread_model = ThreadModel(
                        thread_id=thread_id,
                        created_at=now,
                        updated_at=now,
                        metadata_=metadata,
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

    async def acquire_lock(self, thread_id: str) -> bool:
        """
        原子地尝试获取线程锁（将状态从非 busy 改为 busy）

        使用数据库的原子 UPDATE 操作确保并发安全。
        只有当线程状态不是 busy 时才会成功更新。

        Args:
            thread_id: 线程标识符

        Returns:
            bool: 如果成功获取锁返回 True，否则返回 False

        Raises:
            ResourceNotFoundError: 如果未找到线程。
        """
        async with self.async_session() as session:
            async with session.begin():
                # 首先检查线程是否存在
                result = await session.execute(
                    select(ThreadModel).where(ThreadModel.thread_id == thread_id)
                )
                thread_model = result.scalar_one_or_none()

                if not thread_model:
                    raise ResourceNotFoundError(f"Thread {thread_id} not found")

                # 原子更新：只有当状态不是 busy 时才更新
                result = await session.execute(
                    update(ThreadModel)
                    .where(
                        and_(
                            ThreadModel.thread_id == thread_id,
                            ThreadModel.status != 'busy'
                        )
                    )
                    .values(
                        status='busy',
                        updated_at=datetime.now()
                    )
                )

                # 检查是否有行被更新
                return result.rowcount > 0  # type: ignore
