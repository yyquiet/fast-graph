"""
使用 uvicorn 启动 FastAPI 应用
"""
import logging
import uvicorn

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

    # 使用字符串引用支持热重载
    uvicorn.run(
        "app_demo:app",
        host=host,
        port=port,
        reload=reload,
        log_level="info",
    )


if __name__ == "__main__":
    from src.fast_graph.config import settings
    run_server(host=settings.server_host, port=settings.server_port, reload=True)
