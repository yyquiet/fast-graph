"""
使用 uvicorn 启动 FastAPI 应用
"""

import uvicorn
import logging
import asyncio

# 配置日志
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def run_server(host: str = "0.0.0.0", port: int = 8000, reload: bool = True):
    """
    启动 uvicorn 服务器

    Args:
        host: 监听主机地址，默认 "0.0.0.0"
        port: 监听端口，默认 8000
        reload: 是否启用热重载，默认 True
    """
    logger.info(f"Starting FastGraph server on {host}:{port} with reload={reload}")

    async def main():
        await register_graphs()

        from src.fast_graph.app import app
        config = uvicorn.Config(
            app,
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )

        server = uvicorn.Server(config)
        await server.serve()

    asyncio.run(main())


async def register_graphs():
    from graph_demo import graph
    from src.fast_graph.graph.registry import register_graph
    await register_graph("graph_demo1", graph.graph)
    await register_graph("graph_demo2", graph.graph2)


if __name__ == "__main__":
    run_server(host="0.0.0.0", port=8000, reload=True)
