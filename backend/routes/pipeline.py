from fastapi import APIRouter, status

from backend.schemas import (
    PipelineRunRequest,
    PipelineStartResponse,
    PipelineStatusResponse,
)
from backend.services.pipeline_service import (
    cancel_pipeline,
    pipeline_snapshot,
    reset_pipeline_status,
    start_pipeline,
)

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])


@router.post(
    "/start",
    response_model=PipelineStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_pipeline_route(request: PipelineRunRequest) -> PipelineStartResponse:
    return start_pipeline(request)


@router.get(
    "/status",
    response_model=PipelineStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def pipeline_status_route() -> PipelineStatusResponse:
    return pipeline_snapshot()


@router.post(
    "/reset",
    response_model=PipelineStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def reset_pipeline_status_route() -> PipelineStatusResponse:
    return reset_pipeline_status()


@router.post(
    "/cancel",
    response_model=PipelineStatusResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_pipeline_route() -> PipelineStatusResponse:
    return cancel_pipeline()
