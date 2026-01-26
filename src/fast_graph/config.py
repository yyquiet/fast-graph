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

    # 数据库配置
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


# 创建全局配置实例
settings = Settings()
