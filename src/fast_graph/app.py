from contextlib import asynccontextmanager
import logging
from typing import Dict, Callable, Optional
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from langgraph.graph import StateGraph

from .api import api_router
from .errors import ValidationError, ResourceNotFoundError
from .global_config import GlobalConfig
from .services import AssistantsService


logger = logging.getLogger(__name__)


async def _init_app_resources(
    graphs: Optional[Dict[str, StateGraph]] = None,
    graph_factory: Optional[Callable[[], Dict[str, StateGraph]]] = None,
) -> None:
    """
    初始化应用资源

    Args:
        graphs: 图字典
        graph_factory: 图工厂函数
    """
    logger.info("应用启动")

    # 初始化全局配置
    await GlobalConfig.init_global()

    # 注册图
    if graphs:
        from .graph.registry import register_graph
        for graph_id, graph in graphs.items():
            await register_graph(graph_id, graph)
    elif graph_factory:
        from .graph.registry import register_graph
        graph_dict = graph_factory()
        for graph_id, graph in graph_dict.items():
            await register_graph(graph_id, graph)
    # 初始化assistants，必需在图注册之后
    AssistantsService().init()


async def _cleanup_app_resources() -> None:
    """清理应用资源"""
    logger.info("应用关闭")


def create_app(
    graphs: Optional[Dict[str, StateGraph]] = None,
    graph_factory: Optional[Callable[[], Dict[str, StateGraph]]] = None,
    custom_lifespan: Optional[Callable] = None,
) -> FastAPI:
    """
    创建配置好的 FastAPI 应用实例

    Args:
        graphs: 图字典，key 为 graph_id，value 为 StateGraph 实例
        graph_factory: 图工厂函数，返回图字典（用于延迟加载）
        custom_lifespan: 自定义 lifespan 上下文管理器，会包装在内部 lifespan 外层

    Returns:
        配置好的 FastAPI 应用实例

    Example:
        ```python
        from fast_graph import create_app
        from contextlib import asynccontextmanager

        # 方式1: 直接传入图字典
        app = create_app(graphs={
            "my_graph": my_graph,
        })

        # 方式2: 使用工厂函数
        def create_graphs():
            return {"my_graph": create_my_graph()}

        app = create_app(graph_factory=create_graphs)

        # 方式3: 使用自定义 lifespan
        @asynccontextmanager
        async def my_lifespan(app):
            print("应用层启动")
            yield
            print("应用层关闭")

        app = create_app(
            graph_factory=create_graphs,
            custom_lifespan=my_lifespan
        )
        ```
    """
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        # 如果有自定义 lifespan，先执行
        if custom_lifespan:
            async with custom_lifespan(app):
                # 内部资源初始化
                await _init_app_resources(graphs, graph_factory)
                yield
                # 内部资源清理
                await _cleanup_app_resources()
        else:
            # 没有自定义 lifespan，直接执行内部逻辑
            await _init_app_resources(graphs, graph_factory)
            yield
            await _cleanup_app_resources()

    # 创建 FastAPI 应用
    app = FastAPI(lifespan=lifespan)

    # 注册异常处理器
    @app.exception_handler(ValidationError)
    async def validation_error_handler(_request: Request, exc: ValidationError):
        return JSONResponse(
            status_code=400,
            content={"error": "Validation Error", "detail": str(exc)}
        )

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_error_handler(_request: Request, exc: PydanticValidationError):
        return JSONResponse(
            status_code=400,
            content={"error": "Validation Error", "detail": str(exc)}
        )

    @app.exception_handler(ResourceNotFoundError)
    async def not_found_error_handler(_request: Request, exc: ResourceNotFoundError):
        return JSONResponse(
            status_code=404,
            content={"error": "Not Found", "detail": str(exc)}
        )

    @app.exception_handler(Exception)
    async def error_handler(_request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": "Exception", "detail": str(exc)}
        )

    # 注册路由
    app.include_router(api_router)

    return app


# 创建默认应用实例（用于向后兼容）
app = create_app()
