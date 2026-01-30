from typing import Dict, List, Optional, Union
from langchain_core.runnables.graph import Graph
import threading

from ..graph.registry import get_graph, GRAPHS
from ..models import Assistant, AssistantSearchRequest


class AssistantsService:
    """线程安全的单例 Service"""

    _instance: Optional['AssistantsService'] = None
    _lock = threading.Lock()

    def __new__(cls):
        """单例模式：确保只有一个实例"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.init()
        return cls._instance

    def init(self):
        """初始化 assistants"""
        self.assistants: Dict[str, Assistant] = {}

        for graph_id in GRAPHS.keys():
            assistant = Assistant(
                assistant_id=graph_id,
                graph_id=graph_id,
                name=graph_id,
                description="auto generated assistant",
            )
            self.assistants[assistant.assistant_id] = assistant


    async def search(self, request: AssistantSearchRequest) -> List[Assistant]:
        candidates = []
        for assistant in self.assistants.values():
            candidates.append(assistant)

        # 分页处理
        offset = request.offset if request.offset is not None else 0
        limit = request.limit if request.limit is not None else 10

        start_index = offset
        if start_index >= len(candidates):
            return []
        end_index = offset + limit
        end_index = min(end_index, len(candidates))
        results = candidates[start_index:end_index]

        return results

    async def get_by_id(self, assistant_id: str) -> Optional[Assistant]:
        return self.assistants.get(assistant_id)

    async def get_assistant_graph(
        self, assistant_id: str, xray: Union[bool, int]
    ) -> Optional[Graph]:
        assistant = self.assistants.get(assistant_id)
        if assistant is None:
            return None

        graph = await get_graph(assistant.graph_id)
        if graph is None:
            return None
        else:
            return graph.get_graph(xray=xray)
