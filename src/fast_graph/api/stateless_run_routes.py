"""
Stateless Runs API 路由

无状态运行不需要 thread，每次执行都是独立的，不保存状态
"""
from fastapi import APIRouter, Body, Depends

from ..models import RunCreateStateless
from ..services import StatelessRunsService


router = APIRouter(
    prefix="/runs",
    tags=["Stateless Runs"]
)


# 依赖注入：获取 service 单例
def get_stateless_runs_service() -> StatelessRunsService:
    return StatelessRunsService()


@router.post("/stream")
async def create_stateless_run_stream(
    run_data: RunCreateStateless = Body(...),
    service: StatelessRunsService = Depends(get_stateless_runs_service)
):
    """
    创建无状态运行并流式输出结果

    无状态运行的特点：
    - 不需要 thread_id
    - 不保存执行状态
    - 每次执行都是独立的
    - 适合一次性执行的场景

    Args:
        run_data: 运行配置，包含 assistant_id、input 等
        service: StatelessRunsService 实例

    Returns:
        StreamingResponse: 流式输出的执行结果
    """
    return await service.create_stateless_run_stream(run_data)
