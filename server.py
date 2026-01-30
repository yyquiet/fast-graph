"""
使用 uvicorn 启动 FastAPI 应用

这是一个示例服务器，展示如何使用 fast_graph 包
"""

import uvicorn
import logging
from contextlib import asynccontextmanager

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_graphs():
    """创建所有图的工厂函数"""
    from graph_demo import graph

    return {
        "full_graph": graph.create_full_graph(),
        "normal_graph": graph.create_normal_graph(),
        "hitl_graph": graph.create_hitl_graph(),
        "error_graph": graph.create_error_graph(),
    }


from src.fast_graph import fastGraph
from fastapi import FastAPI


@asynccontextmanager
async def custom_lifespan(app: FastAPI):
    """应用层的自定义 lifespan"""
    logger.info("🚀 应用层启动 - 开始")

    # 在这里可以做应用层的初始化
    # 例如：连接外部服务、加载额外配置、初始化缓存等

    yield  # 应用运行期间

    # 在这里可以做应用层的清理
    # 例如：关闭连接、清理资源等
    logger.info("👋 应用层关闭")


# 创建应用，传入自定义 lifespan
app = fastGraph(
    graph_factory=create_graphs,
    custom_lifespan=custom_lifespan
)


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = True):
    """
    启动 uvicorn 服务器

    Args:
        host: 监听主机地址，默认 "0.0.0.0"
        port: 监听端口，默认 8000
        reload: 是否启用热重载，默认 True
    """
    logger.info(f"Starting FastGraph server on {host}:{port} with reload={reload}")

    # 使用字符串引用支持热重载
    uvicorn.run(
        "server:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    from src.fast_graph.config import settings
    run_server(host=settings.server_host, port=settings.server_port, reload=True)
