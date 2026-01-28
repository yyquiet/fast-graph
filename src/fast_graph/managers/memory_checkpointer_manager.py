from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver
from .base_checkpointer_manager import BaseCheckpointerManager


class MemoryCheckpointerManager(BaseCheckpointerManager):
    """
    内存 Checkpointer 管理器
    """

    def __init__(self):
       pass

    def get_checkpointer(self) -> BaseCheckpointSaver:
        return InMemorySaver()
