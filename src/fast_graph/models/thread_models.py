from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ThreadCreate(BaseModel):
    thread_id: Optional[str] = Field(
        None,
        description='The ID of thread. If not provided, a random UUID will be generated.',
        title='Thread Id',
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description='Metadata to add to thread.', title='Metadata'
    )
    if_exists: Optional[str] = Field(
        "raise",
        description="How to handle duplicate creation. Must be either 'raise' (raise error if duplicate), or 'do_nothing' (return existing thread).",
        title='If Exists',
    )


class ThreadStatus(Enum):
    idle = 'idle'
    busy = 'busy'
    interrupted = 'interrupted'
    error = 'error'


class Thread(BaseModel):
    thread_id: str = Field(..., description='The ID of thread.', title='Thread Id')
    created_at: datetime = Field(
        ..., description='The time thread was created.', title='Created At'
    )
    updated_at: datetime = Field(
        ..., description='The last time thread was updated.', title='Updated At'
    )
    metadata: Dict[str, Any] = Field(
        ..., description='The thread metadata.', title='Metadata'
    )
    status: ThreadStatus = Field(
        ..., description='The status of thread.', title='Status'
    )


class ThreadSearchRequest(BaseModel):
    ids: Optional[List[str]] = Field(
        None,
        description='List of thread IDs to include. Others are excluded.',
        title='Ids',
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description='Thread metadata to filter on.', title='Metadata'
    )
    status: Optional[ThreadStatus] = Field(
        None, description='Thread status to filter on.', title='Status'
    )
    limit: Optional[int] = Field(
        10, description='Maximum number to return.', title='Limit',
        ge=1, le=1000
    )
    offset: Optional[int] = Field(
        0, description='Offset to start from.', title='Offset',
        ge=0
    )
