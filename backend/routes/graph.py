from fastapi import APIRouter, status

from backend.schemas import GraphResponse
from backend.services.graph_service import read_graph

router = APIRouter(prefix="/api", tags=["graph"])


@router.get("/graph", response_model=GraphResponse, status_code=status.HTTP_200_OK)
async def get_graph() -> GraphResponse:
    return read_graph()
