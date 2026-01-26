from typing import List
from fastapi import APIRouter, Path, Depends

from ..models import (
    Thread,
    ThreadCreate,
    ThreadSearchRequest,
)
from ..services import ThreadsService

router = APIRouter(
    prefix="/threads",
    tags=["Threads"]
)


# 依赖注入：获取 service 单例
def get_threads_service() -> ThreadsService:
    return ThreadsService()


@router.post("", response_model=Thread)
async def create_thread(
    request: ThreadCreate,
    service: ThreadsService = Depends(get_threads_service)
):
    """Create a thread."""
    return await service.create_thread(request)


@router.post("/search", response_model=List[Thread])
async def search_threads(
    request: ThreadSearchRequest,
    service: ThreadsService = Depends(get_threads_service)
):
    """Search for threads.

    This endpoint also functions as the endpoint to list all threads.
    """
    return await service.search(request)


@router.get("/{thread_id}", response_model=Thread)
async def get_thread(
    thread_id: str = Path(..., description='The ID of the thread.'),
    service: ThreadsService = Depends(get_threads_service)
):
    """Get a thread by ID."""
    return await service.get(thread_id)
