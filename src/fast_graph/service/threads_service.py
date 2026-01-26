from typing import List, Optional
import threading

from ..model import (
    Thread,
    ThreadCreate,
    ThreadSearchRequest,
)
from ..global_config import GlobalConfig


class ThreadsService:
    """线程安全的单例 Service"""

    _instance: Optional['ThreadsService'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式：确保只有一个实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """初始化 threads（只执行一次）"""
        pass

    async def create_thread(self, request: ThreadCreate) -> Thread:
        """Create a thread."""
        return await GlobalConfig.global_threads_manager.create(
            thread_id=request.thread_id,
            metadata=request.metadata,
            if_exists=request.if_exists,
        )


    async def search(self, request: ThreadSearchRequest) -> List[Thread]:
        """Search for threads."""
        limit = request.limit if request.limit else 10
        offset = request.offset if request.offset else 0
        return await GlobalConfig.global_threads_manager.search(
            ids=request.ids,
            metadata=request.metadata,
            status=request.status,
            limit=limit,
            offset=offset,
        )

    async def get(self, thread_id: str) -> Optional[Thread]:
        """Get a thread by ID."""
        return await GlobalConfig.global_threads_manager.get(thread_id)

