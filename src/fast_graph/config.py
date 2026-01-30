"""
配置管理模块
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置类，从环境变量中读取配置"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    server_host: str = Field(
        default="localhost",
        description="服务器主机地址"
    )
    server_port: int = Field(
        default=8000,
        description="服务器端口号"
    )

    # 数据库配置
    postgre_auto_create_tables: bool = Field(
        default=True,
        description="自动创建表"
    )
    postgre_database_url: str = Field(
        default="",
        description="PostgreSQL 数据库连接 URL"
    )
    postgre_db_pool_size: int = Field(
        default=10,
        description="数据库连接池大小"
    )
    postgre_db_max_overflow: int = Field(
        default=20,
        description="数据库连接池最大溢出连接数"
    )
    postgre_db_echo: bool = Field(
        default=False,
        description="是否打印 SQL 语句"
    )

    # redis配置
    redis_host: str = Field(
        default="",
        description="Redis 主机地址"
    )
    redis_port: int = Field(
        default=6379,
        description="Redis 端口号"
    )
    redis_username: str = Field(
        default="",
        description="Redis 用户"
    )
    redis_password: str = Field(
        default="",
        description="Redis 密码"
    )
    redis_db: int = Field(
        default=0,
        description="Redis 数据库号"
    )
    redis_max_connections: int = Field(
        default=20,
        description="Redis 最大连接数"
    )
    redis_key_pre: str = Field(
        default="fast-graph",
        description="Redis key 前缀"
    )

# 创建全局配置实例
settings = Settings()
