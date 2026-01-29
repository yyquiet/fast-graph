from typing import List, Optional, Union, Dict, Any
from enum import Enum

from pydantic import BaseModel, Field


class Config(BaseModel):
    tags: Optional[List[str]] = Field(None, title='Tags')
    recursion_limit: Optional[int] = Field(None, title='Recursion Limit')
    configurable: Optional[Dict[str, Any]] = Field(None, title='Configurable')


class Send(BaseModel):
    node: str = Field(..., description='The node to send message to.', title='Node')
    input: Optional[Union[Dict[str, Any], List[Any], float, str, bool]] = Field(
        ..., description='The message to send.', title='Message'
    )


class Command(BaseModel):
    update: Optional[Union[Dict[str, Any], List[Any]]] = Field(
        None, description='An update to state.', title='Update'
    )
    resume: Optional[Union[Dict[str, Any], List[Any], float, str, bool]] = Field(
        None, description='A value to pass to an interrupted node.', title='Resume'
    )
    goto: Optional[Union[Send, List[Send], str, List[str]]] = Field(
        None,
        description='Name of node(s) to navigate to next or node(s) to be executed with a provided input.',
        title='Goto',
    )


class CheckpointConfig(BaseModel):
    thread_id: Optional[str] = Field(
        None,
        description='Unique identifier for thread associated with this checkpoint.',
        title='Thread Id',
    )
    checkpoint_ns: Optional[str] = Field(
        None,
        description='Namespace for checkpoint, used for organization and retrieval.',
        title='Checkpoint Namespace',
    )
    checkpoint_id: Optional[str] = Field(
        None, description='Optional unique identifier for checkpoint itself.', title='Checkpoint Id'
    )
    checkpoint_map: Optional[Dict[str, Any]] = Field(
        None, description='Optional dictionary containing checkpoint-specific data.', title='Checkpoint Map'
    )


class StreamMode(Enum):
    values = 'values'
    messages = 'messages'
    messages_tuple = 'messages-tuple'
    tasks = 'tasks'
    checkpoints = 'checkpoints'
    updates = 'updates'
    events = 'events'
    debug = 'debug'
    custom = 'custom'


class Interrupt(BaseModel):
    id: Optional[str] = None
    value: Dict[str, Any]


class RunCreateStateful(BaseModel):
    assistant_id: str = Field(
        ...,
        description='The assistant ID or graph name to run. If using graph name, will default to first assistant created from that graph.',
    )
    checkpoint: Optional[CheckpointConfig] = Field(
        None, description='The checkpoint to resume from.', title='Checkpoint'
    )
    input: Optional[Union[Dict[str, Any], List, str, float, bool]] = Field(
        None, description='The input to the graph.', title='Input'
    )
    command: Optional[Command] = Field(
        None, description='The input to the graph.', title='Input'
    )
    config: Optional[Config] = Field(
        None, description='The configuration for the assistant.', title='Config'
    )
    context: Optional[Dict[str, Any]] = Field(
        None, description='Static context added to the assistant.', title='Context'
    )
    interrupt_before: Optional[Union[str, List[str]]] = Field(
        None,
        description='Nodes to interrupt immediately before they get executed.',
        title='Interrupt Before',
    )
    interrupt_after: Optional[Union[str, List[str]]] = Field(
        None,
        description='Nodes to interrupt immediately after they get executed.',
        title='Interrupt After',
    )
    stream_mode: Optional[Union[List[StreamMode], StreamMode]] = Field(
        StreamMode.values, description='The stream mode(s) to use.', title='Stream Mode'
    )
    stream_subgraphs: Optional[bool] = Field(
        False,
        description='Whether to stream output from subgraphs.',
        title='Stream Subgraphs',
    )
    if_not_exists: Optional[str] = Field(
        'reject',
        description="How to handle missing thread. Must be either 'reject' (raise error if missing), or 'create' (create new thread).",
        title='If Not Exists',
    )
