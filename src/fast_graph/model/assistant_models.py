from typing import Optional
from pydantic import BaseModel, Field


class Assistant(BaseModel):
    assistant_id: str = Field(
        ..., description='The ID of the assistant.', title='Assistant Id'
    )
    graph_id: str = Field(..., description='The ID of the graph.', title='Graph Id')
    name: Optional[str] = Field(
        None, description='The name of the assistant', title='Assistant Name'
    )
    description: Optional[str] = Field(
        None,
        description='The description of the assistant',
        title='Assistant Description',
    )

class AssistantSearchRequest(BaseModel):
    limit: Optional[int] = Field(
        10, description='The maximum number of results to return.', title='Limit',
        ge=1, le=1000
    )
    offset: Optional[int] = Field(
        0, description='The number of results to skip.', title='Offset',
        ge=0
    )
