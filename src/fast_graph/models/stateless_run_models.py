"""
Stateless Run 相关的数据模型
"""
from typing import List, Optional, Union, Dict, Any
from pydantic import BaseModel, Field

from .run_models import Config, StreamMode


class RunCreateStateless(BaseModel):
    """
    创建无状态运行的请求模型

    无状态运行不需要 thread_id，每次执行都是独立的，不保存状态
    """
    assistant_id: str = Field(
        ...,
        description='The assistant ID or graph name to run.',
    )
    input: Optional[Union[Dict[str, Any], List, str, float, bool]] = Field(
        None, description='The input to the graph.', title='Input'
    )
    config: Optional[Config] = Field(
        None, description='The configuration for the assistant.', title='Config'
    )
    context: Optional[Dict[str, Any]] = Field(
        None, description='Static context added to the assistant.', title='Context'
    )
    stream_mode: Optional[Union[List[StreamMode], StreamMode]] = Field(
        StreamMode.values, description='The stream mode(s) to use.', title='Stream Mode'
    )
    stream_subgraphs: Optional[bool] = Field(
        False,
        description='Whether to stream output from subgraphs.',
        title='Stream Subgraphs',
    )
