from abc import ABC, abstractmethod
from langgraph.checkpoint.postgres.base import BasePostgresSaver

class BaseCheckpointerManager(ABC):
    """
    Checkpointer 管理器抽象基类。
    """

    @abstractmethod
    def get_checkpointer(self) -> BasePostgresSaver:
        """
        获取 Checkpointer 实例
        """
        pass
