"""
Fast Graph - 快速构建 LangGraph FastAPI 服务

这个包提供了简单的方式来将 LangGraph 图转换为 FastAPI 服务
"""

from typing import Dict, Callable, Optional
from fastapi import FastAPI
from langgraph.graph import StateGraph

# 导入核心功能
from .app import create_app
from .graph.registry import register_graph


__version__ = "0.1.0"


# 导出核心功能
__all__ = [
    "fastGraph",
    "register_graph",
    "create_app",
]


def fastGraph(
    graphs: Optional[Dict[str, StateGraph]] = None,
    graph_factory: Optional[Callable[[], Dict[str, StateGraph]]] = None,
    custom_lifespan: Optional[Callable] = None,
) -> FastAPI:
    """
    快速创建 FastGraph 应用（create_app 的别名）

    这是最简单的使用方式，一行代码即可创建完整的 FastAPI 应用

    Args:
        graphs: 图字典，key 为 graph_id，value 为 StateGraph 实例
        graph_factory: 图工厂函数，返回图字典（用于延迟加载）
        custom_lifespan: 自定义 lifespan 上下文管理器，会包装在内部 lifespan 外层

    Returns:
        配置好的 FastAPI 应用实例

    Example:
        ```python
        from langgraph.graph import StateGraph
        from fast_graph import fastGraph
        from contextlib import asynccontextmanager

        # 创建你的图
        my_graph = StateGraph(MyState)
        # ... 构建图 ...

        # 方式1: 一行代码创建 FastAPI 应用
        app = fastGraph(graphs={"my_graph": my_graph})

        # 方式2: 使用自定义 lifespan
        @asynccontextmanager
        async def my_lifespan(app):
            print("应用层启动")
            yield
            print("应用层关闭")

        app = fastGraph(
            graphs={"my_graph": my_graph},
            custom_lifespan=my_lifespan
        )

        # 使用 uvicorn 启动
        # uvicorn main:app --reload
        ```
    """
    return create_app(graphs=graphs, graph_factory=graph_factory, custom_lifespan=custom_lifespan)
