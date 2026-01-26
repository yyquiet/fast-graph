"""
存储后端的基础接口。

本模块定义了所有存储后端实现必须实现的抽象基类，
确保不同存储类型之间的行为一致性。
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from ..models import Thread, ThreadStatus

class BaseThreadsManager(ABC):
    """
    线程管理器的抽象基类。

    线程管理器处理线程和运行的生命周期和状态，
    包括创建、检索、更新和删除。
    """

    @abstractmethod
    async def setup(self) -> None:
        """
        初始化线程管理器。

        此方法应创建线程管理所需的必要表、连接或数据结构。
        """
        pass

    @abstractmethod
    async def create(
        self,
        thread_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        if_exists: Optional[str] = None
    ) -> Thread:
        """
        创建新线程。

        Args:
            thread_id: 可选的线程 ID。如果为 None，将生成 UUID。
            metadata: 要附加到线程的可选元数据。
            if_exists: 当线程已存在时的行为 ('raise', 'do_nothing'), 默认raise。

        Returns:
            创建的 Thread 对象。
            如果线程已存在且 if_exists='do_nothing' 返回已有对象

        Raises:
            ResourceExistsError: 如果线程已存在且 if_exists='raise'
        """
        pass

    @abstractmethod
    async def get(self, thread_id: str) -> Thread:
        """
        通过 ID 检索线程。

        Args:
            thread_id: 线程标识符

        Returns:
            Thread 对象。

        Raises:
            ResourceNotFoundError: 如果未找到线程。
        """
        pass

    @abstractmethod
    async def search(
        self,
        ids: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        status: Optional[ThreadStatus] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> List[Thread]:
        """
        搜索具有过滤和分页的线程。

        Args:
            ids: 可选的线程 ID 列表
            metadata: 可选的元数据过滤器
            status: 可选的状态过滤器
            limit: 返回的最大结果数
            offset: 要跳过的结果数

        Returns:
            符合条件的 Thread 对象列表。
        """
        pass

    @abstractmethod
    async def update(
        self,
        thread_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """
        更新线程的属性。

        Args:
            thread_id: 线程标识符
            updates: 要更新的字段字典

        Raises:
            ResourceNotFoundError: 如果未找到线程。
        """
        pass

    @abstractmethod
    async def delete(self, thread_id: str) -> None:
        """
        删除线程。

        Args:
            thread_id: 线程标识符

        Raises:
            ResourceNotFoundError: 如果未找到线程。
        """
        pass
