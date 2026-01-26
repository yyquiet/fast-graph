from typing import Optional
import threading

from ..models import (
    RunCreateStateful,
)


class RunsService:
    """线程安全的单例 Service"""

    _instance: Optional['RunsService'] = None
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
        """初始化 runs（只执行一次）"""
        pass


    async def create_run_stream(
        self,
        thread_id: str,
        run_data: RunCreateStateful
    ):
        """Create a run in existing thread. Stream the output."""
        pass
