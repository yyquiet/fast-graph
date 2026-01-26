from fastapi import APIRouter
from .assistant_routes import router as assistant_router


# 创建总路由
api_router = APIRouter()

# 注册所有子路由
api_router.include_router(assistant_router)
