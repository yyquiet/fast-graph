from typing import List, Dict, Any, Union
from fastapi import APIRouter, Path, Query, Depends

from ..model import (
    Assistant,
    AssistantSearchRequest,
)
from ..service import AssistantsService

router = APIRouter(
    prefix="/assistants",
    tags=["Assistants"]
)


# 依赖注入：获取 service 单例
def get_assistants_service() -> AssistantsService:
    return AssistantsService()


@router.post("/search", response_model=List[Assistant])
async def search_assistants(
    request: AssistantSearchRequest,
    service: AssistantsService = Depends(get_assistants_service)
):
    """Search for assistants.

    This endpoint also functions as the endpoint to list all assistants.
    """
    return await service.search(request)


@router.get("/{assistant_id}/graph", response_model=Dict[str, List[Dict[str, Any]]])
async def get_assistant_graph(
    assistant_id: str = Path(..., description="The ID of the assistant or the ID of the graph."),
    xray: Union[bool, int] = Query(False, description="Include graph representation of subgraphs. If an integer value is provided, only subgraphs with a depth less than or equal to the value will be included."),
    service: AssistantsService = Depends(get_assistants_service)
):
    """Get an assistant by ID."""
    res = await service.get_assistant_graph(assistant_id, xray)
    if res is None:
        return None
    else:
        return res.to_json()
