from typing import List
from fastapi import APIRouter, Path, Depends, Query, Body

from ..models import (
    Thread,
    ThreadCreate,
    ThreadSearchRequest,
    ThreadState,
    ThreadStateUpdate,
    ThreadStateUpdateResponse,
    ThreadStateCheckpointRequest,
    ThreadStateSearch,
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

@router.get("/{thread_id}/state", response_model=ThreadState)
async def get_latest_thread_state(
    thread_id: str = Path(..., description='The ID of the thread.'),
    subgraphs: bool = Query(None, description='Whether to include subgraphs in the response.'),
    service: ThreadsService = Depends(get_threads_service)
):
    """Get state for a thread.

    The latest state of the thread (i.e. latest checkpoint) is returned.
    """
    return await service.get_latest_state(thread_id, subgraphs)


@router.post("/{thread_id}/state", response_model=ThreadStateUpdateResponse)
async def update_thread_state(
    thread_id: str = Path(..., description='The ID of the thread.'),
    request: ThreadStateUpdate = Body(...),
    service: ThreadsService = Depends(get_threads_service)
):
    """Add state to a thread."""
    return await service.update_state(thread_id, request)


@router.get("/{thread_id}/state/{checkpoint_id}", response_model=ThreadState)
async def get_thread_state_at_checkpoint(
    thread_id: str = Path(..., description='The ID of the thread.'),
    checkpoint_id: str = Path(..., description='The ID of the checkpoint.'),
    subgraphs: bool = Query(None, description='Whether to include subgraphs in the response.'),
    service: ThreadsService = Depends(get_threads_service)
):
    """Get state for a thread at a specific checkpoint."""
    return await service.get_state_at_checkpoint(thread_id, checkpoint_id, subgraphs)


@router.post("/{thread_id}/state/checkpoint", response_model=ThreadState)
async def get_thread_state_at_checkpoint_post(
    thread_id: str = Path(..., description='The ID of the thread.'),
    request: ThreadStateCheckpointRequest = Body(...),
    subgraphs: bool = Query(None, description='If true, includes subgraph states.'),
    service: ThreadsService = Depends(get_threads_service)
):
    """Get state for a thread at a specific checkpoint."""
    return await service.get_state_at_checkpoint_post(thread_id, request, subgraphs)


@router.get("/{thread_id}/history", response_model=List[ThreadState])
async def get_thread_history(
    thread_id: str = Path(..., description='The ID of the thread.'),
    limit: int = Query(10, description='Limit to number of results to return.'),
    before: str = Query(None, description='Get history before this checkpoint.'),
    service: ThreadsService = Depends(get_threads_service)
):
    """Get all past states for a thread."""
    return await service.get_history(thread_id, limit, before)


@router.post("/{thread_id}/history", response_model=List[ThreadState])
async def get_thread_history_post(
    thread_id: str = Path(..., description='The ID of the thread.'),
    request: ThreadStateSearch = Body(...),
    service: ThreadsService = Depends(get_threads_service)
):
    """Get all past states for a thread."""
    return await service.get_history_post(thread_id, request)
