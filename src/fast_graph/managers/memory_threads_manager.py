"""
内存线程管理器

用于测试和开发环境的内存版本线程管理器。
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

from .base_threads_manager import BaseThreadsManager
from ..models import Thread, ThreadStatus
from ..errors import ResourceNotFoundError, ResourceExistsError


class MemoryThreadsManager(BaseThreadsManager):
    """
    内存线程管理器

    将线程数据存储在内存中，适用于测试和开发环境。
    不需要外部数据库依赖。
    """

    def __init__(self):
        """初始化内存线程管理器"""
        self._threads: Dict[str, Thread] = {}
        self._initialized = False

    async def setup(self) -> None:
        """
        初始化线程管理器

        对于内存管理器，这个方法只是标记为已初始化。
        """
        self._initialized = True

    async def create(
        self,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        if_exists: Optional[str] = None
    ) -> Thread:
        """
        创建新线程

        Args:
            thread_id: 可选的线程 ID。如果为 None，将生成 UUID。
            metadata: 要附加到线程的可选元数据。
            if_exists: 当线程已存在时的行为 ('raise', 'do_nothing'), 默认 raise。

        Returns:
            创建的 Thread 对象。
            如果线程已存在且 if_exists='do_nothing' 返回已有对象

        Raises:
            ResourceExistsError: 如果线程已存在且 if_exists='raise'
        """
        # 生成或使用提供的 thread_id
        if thread_id is None:
            thread_id = str(uuid.uuid4())

        # 检查线程是否已存在
        if thread_id in self._threads:
            if if_exists == "do_nothing":
                return self._threads[thread_id]
            else:
                raise ResourceExistsError(f"Thread {thread_id} already exists")

        # 创建新线程
        now = datetime.now()
        thread = Thread(
            thread_id=thread_id,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
            status=ThreadStatus.idle
        )

        # 存储线程
        self._threads[thread_id] = thread

        return thread

    async def get(self, thread_id: str) -> Thread:
        """
        通过 ID 检索线程

        Args:
            thread_id: 线程标识符

        Returns:
            Thread 对象。

        Raises:
            ResourceNotFoundError: 如果未找到线程。
        """
        if thread_id not in self._threads:
            raise ResourceNotFoundError(f"Thread {thread_id} not found")

        return self._threads[thread_id]

    async def search(
        self,
        ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: Optional[ThreadStatus] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Thread]:
        """
        搜索具有过滤和分页的线程

        Args:
            ids: 可选的线程 ID 列表
            metadata: 可选的元数据过滤器
            status: 可选的状态过滤器
            limit: 返回的最大结果数
            offset: 要跳过的结果数

        Returns:
            符合条件的 Thread 对象列表。
        """
        results = []

        for thread in self._threads.values():
            # 过滤 IDs
            if ids is not None and thread.thread_id not in ids:
                continue

            # 过滤状态
            if status is not None and thread.status != status:
                continue

            # 过滤元数据
            if metadata is not None:
                match = True
                for key, value in metadata.items():
                    if key not in thread.metadata or thread.metadata[key] != value:
                        match = False
                        break
                if not match:
                    continue

            results.append(thread)

        # 应用分页
        return results[offset:offset + limit]

    async def update(
        self,
        thread_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """
        更新线程的属性

        Args:
            thread_id: 线程标识符
            updates: 要更新的字段字典

        Raises:
            ResourceNotFoundError: 如果未找到线程。
        """
        if thread_id not in self._threads:
            raise ResourceNotFoundError(f"Thread {thread_id} not found")

        thread = self._threads[thread_id]

        # 更新字段
        if "status" in updates:
            thread.status = updates["status"]

        if "metadata" in updates:
            # 合并元数据
            if isinstance(updates["metadata"], dict):
                thread.metadata.update(updates["metadata"])
            else:
                thread.metadata = updates["metadata"]

        # 更新时间戳
        thread.updated_at = datetime.now()

    async def delete(self, thread_id: str) -> None:
        """
        删除线程

        Args:
            thread_id: 线程标识符

        Raises:
            ResourceNotFoundError: 如果未找到线程。
        """
        if thread_id not in self._threads:
            raise ResourceNotFoundError(f"Thread {thread_id} not found")

        del self._threads[thread_id]

    def clear(self) -> None:
        """
        清除所有线程数据

        这是一个辅助方法，用于测试环境中清理数据。
        """
        self._threads.clear()

    def count(self) -> int:
        """
        获取线程总数

        这是一个辅助方法，用于测试和调试。

        Returns:
            线程总数
        """
        return len(self._threads)
