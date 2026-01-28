from fastapi import APIRouter
from .assistant_routes import router as assistant_router
from .thread_routes import router as thread_router
from .run_routes import router as run_router
from .stateless_run_routes import router as stateless_run_router


# 创建总路由
api_router = APIRouter()

# 注册所有子路由
api_router.include_router(assistant_router)
api_router.include_router(thread_router)
api_router.include_router(run_router)
api_router.include_router(stateless_run_router)
