from typing import Dict, Optional
from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import StateGraph
from langchain_core.runnables.config import (
    RunnableConfig,
)


# 全局图注册表
GRAPHS: Dict[str, StateGraph] = {}


async def register_graph(
    graph_id: str,
    graph: StateGraph
) -> None:
    """
    注册图到全局注册表

    Args:
        graph_id: 图的唯一标识符
        graph: 图
    """
    GRAPHS[graph_id] = graph


async def get_graph(
    graph_id: str,
    config: Optional[RunnableConfig] = None
) -> Optional[CompiledStateGraph]:
    """
    获取已注册的图实例

    每次调用都会重新编译图，返回独立的实例，避免状态污染

    Args:
        graph_id: 图的唯一标识符
        config: 运行配置

    Returns:
        编译后的图实例（每次都是新实例）
    """
    if graph_id not in GRAPHS:
        return None

    state_graph = GRAPHS[graph_id]

    # 每次都重新编译，确保返回独立的图实例
    compiled = state_graph.compile()
    compiled.config = config

    return compiled
