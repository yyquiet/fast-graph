"""
Stateless Runs Service

处理无状态运行的业务逻辑
"""
from typing import Optional
import threading

from ..models import RunCreateStateless
from ..graph.executor import GraphExecutor
from ..global_config import GlobalConfig


class StatelessRunsService:
    """
    无状态运行服务（线程安全的单例）

    无状态运行不需要 thread，不保存状态，每次执行都是独立的
    """

    _instance: Optional['StatelessRunsService'] = None
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
        """初始化服务（只执行一次）"""
        pass

    async def create_stateless_run_stream(
        self,
        run_data: RunCreateStateless
    ):
        """
        创建无状态运行并流式输出结果

        Args:
            run_data: 运行配置

        Returns:
            StreamingResponse: 流式输出的执行结果
        """
        pass
