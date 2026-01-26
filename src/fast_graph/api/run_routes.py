from fastapi import APIRouter, Path, Body, Depends

from ..models import (
    RunCreateStateful,
)
from ..services import RunsService


router = APIRouter(
    prefix="/threads",
    tags=["Thread Runs"]
)


# 依赖注入：获取 service 单例
def get_runs_service() -> RunsService:
    return RunsService()


@router.post("/{thread_id}/runs/stream")
async def create_run_stream_output(
    thread_id: str = Path(..., description="The ID of the thread."),
    run_data: RunCreateStateful = Body(...),
    service: RunsService = Depends(get_runs_service)
):
    """
    Create a run in existing thread. Stream the output.
    """
    return await service.create_run_stream(thread_id, run_data)


