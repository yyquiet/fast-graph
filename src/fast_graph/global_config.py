"""全局配置和初始化模块"""

import logging

from .config import settings
from .managers import (
    BaseThreadsManager,
    PostgresThreadsManager,
    StreamQueueManager,
    RedisStreamQueue,
    BaseCheckpointerManager,
    PostgresCheckpointerManager,
)
logger = logging.getLogger(__name__)


# 全局配置类
class GlobalConfig:
    """全局配置管理"""
    global_threads_manager: BaseThreadsManager
    global_queue_manager: StreamQueueManager
    global_checkpointer_manager: BaseCheckpointerManager
    is_initialized: bool = False

    @classmethod
    async def init(cls):
        """根据环境变量初始化线程管理器"""

        if settings.postgre_database_url:
            # 使用 PostgreSQL 作为存储后端
            logger.info("使用 PostgreSQL 作为存储后端")
            cls.global_threads_manager = PostgresThreadsManager()
            # 初始化数据库表
            logger.info("初始化数据库表")
            await cls.global_threads_manager.setup()

            cls.global_checkpointer_manager = PostgresCheckpointerManager()
            await cls.global_checkpointer_manager.init()
        else:
            # 没有配置任何存储后端，抛出错误
            raise ValueError(
                "未配置存储后端。请设置以下环境变量之一：\n"
                "  - POSTGRE_DATABASE_URL: PostgreSQL 数据库连接 URL"
            )

        if settings.redis_host:
            logger.info("使用 Redis 作为消息队列")
            cls.global_queue_manager = StreamQueueManager(RedisStreamQueue)
        else:
            raise ValueError(
                "未配置消息队列。请设置以下环境变量之一：\n"
                "  - REDIS_HOST: Redis 服务器地址"
            )

    @classmethod
    async def init_global(cls) -> None:
        """初始化全局组件"""
        if cls.is_initialized:
            logger.info("全局配置已初始化，跳过")
            return

        logger.info("开始初始化全局配置")

        # 初始化线程管理器
        await cls.init()

        cls.is_initialized = True
        logger.info("全局配置初始化完成")
