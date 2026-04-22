from fastapi import APIRouter, status

from backend.schemas import QdrantInfoResponse, QdrantOpenResponse
from backend.services.qdrant_service import qdrant_info, qdrant_public_url

router = APIRouter(prefix="/api/qdrant", tags=["qdrant"])


@router.get("/info", response_model=QdrantInfoResponse, status_code=status.HTTP_200_OK)
async def qdrant_info_route() -> QdrantInfoResponse:
    return qdrant_info()


@router.post("/open", response_model=QdrantOpenResponse, status_code=status.HTTP_200_OK)
async def qdrant_open_route() -> QdrantOpenResponse:
    return QdrantOpenResponse(status="ok", url=qdrant_public_url())
