from abc import ABC, abstractmethod
from langgraph.checkpoint.base import BaseCheckpointSaver

class BaseCheckpointerManager(ABC):
    """
    Checkpointer 管理器抽象基类。
    """

    @abstractmethod
    def get_checkpointer(self) -> BaseCheckpointSaver:
        """
        获取 Checkpointer 实例
        """
        pass
