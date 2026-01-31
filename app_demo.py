"""
这是一个示例，展示如何使用 fast_graph 包
"""
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
        "chat_graph": graph.create_chat_graph(),
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
