from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field
from .run_models import CheckpointConfig, Interrupt


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

class ThreadStateCheckpointRequest(BaseModel):
    checkpoint: CheckpointConfig = Field(
        ..., description='The checkpoint to get the state for.', title='Checkpoint'
    )
    subgraphs: Optional[bool] = Field(
        None, description='Include subgraph states.', title='Subgraphs'
    )


class ThreadStateSearch(BaseModel):
    limit: Optional[int] = Field(
        10, description='The maximum number of states to return.', title='Limit',
        ge=1, le=1000
    )
    before: Optional[CheckpointConfig] = Field(
        None, description='Return states before this checkpoint.', title='Before'
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None, description='Filter states by metadata key-value pairs.', title='Metadata'
    )
    checkpoint: Optional[CheckpointConfig] = Field(
        None, description='Return states for this subgraph.', title='Checkpoint'
    )


class ThreadStateUpdate(BaseModel):
    values: Optional[Union[List, Dict[str, Any]]] = Field(
        None, description='The values to update the state with.', title='Values'
    )
    checkpoint: Optional[CheckpointConfig] = Field(
        None, description='The checkpoint to update the state of.', title='Checkpoint'
    )
    as_node: Optional[str] = Field(
        None,
        description='Update the state as if this node had just executed.',
        title='As Node',
    )


class ThreadState(BaseModel):
    values: Union[List[Dict[str, Any]], Dict[str, Any]] = Field(..., title='Values')
    next: List[str] = Field(..., title='Next')
    tasks: Optional[List['Task']] = Field(None, title='Tasks')
    checkpoint: CheckpointConfig = Field(..., title='Checkpoint')
    metadata: Dict[str, Any] = Field(..., title='Metadata')
    created_at: str = Field(..., title='Created At')
    parent_checkpoint: Optional[Dict[str, Any]] = Field(None, title='Parent Checkpoint')
    interrupts: Optional[List[Interrupt]] = None


class Task(BaseModel):
    id: str = Field(..., title='Task Id')
    name: str = Field(..., title='Node Name')
    error: Optional[str] = Field(None, title='Error')
    interrupts: Optional[List[Interrupt]] = None
    checkpoint: Optional[CheckpointConfig] = Field(None, title='Checkpoint')
    state: Optional[ThreadState] = None


class ThreadStateUpdateResponse(BaseModel):
    checkpoint: CheckpointConfig = Field(..., title='Checkpoint')


# 更新前向引用
ThreadState.model_rebuild()
