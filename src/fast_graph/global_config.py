"""全局配置和初始化模块"""

from langgraph.checkpoint.base import BaseCheckpointSaver
from .manager import BaseThreadsManager

# 全局配置类
class GlobalConfig:
    """全局配置管理"""
    global_threads_manager: BaseThreadsManager
    global_checkpointer: BaseCheckpointSaver
    is_initialized: bool = False

    @classmethod
    def init(cls):
        pass

    @classmethod
    async def init_global(cls) -> None:
        """初始化全局组件"""
        if cls.is_initialized:
            return

        cls.init()

        cls.is_initialized = True
