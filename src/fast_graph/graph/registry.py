from typing import Dict, Optional, Union
from langgraph.graph.state import CompiledStateGraph
from langgraph.graph import StateGraph
from langchain_core.runnables.config import (
    RunnableConfig,
)


# 全局图注册表
GRAPHS: Dict[str, Union[StateGraph, CompiledStateGraph]] = {}


async def register_graph(
    graph_id: str,
    graph: Union[StateGraph, CompiledStateGraph]
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

    Args:
        graph_id: 图的唯一标识符
        config: 运行配置

    Returns:
        编译后的图实例
    """
    if graph_id not in GRAPHS:
        return None

    compiled = GRAPHS[graph_id]
    if isinstance(compiled, StateGraph):
        compiled = compiled.compile()

    compiled.config = config

    return compiled
