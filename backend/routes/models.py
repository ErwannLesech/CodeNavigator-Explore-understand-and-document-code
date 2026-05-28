from fastapi import APIRouter, status

from backend.schemas import ChatModelOption, ChatModelsResponse
from src.rag.providers import list_available_models, resolve_default_model

router = APIRouter(prefix="/api", tags=["models"])


@router.get(
    "/models", response_model=ChatModelsResponse, status_code=status.HTTP_200_OK
)
@router.get(
    "/chat/models", response_model=ChatModelsResponse, status_code=status.HTTP_200_OK
)
async def list_models() -> ChatModelsResponse:
    models = list_available_models()
    if not models:
        return ChatModelsResponse(default_provider="", default_model="", models=[])

    default_model = resolve_default_model(models)
    return ChatModelsResponse(
        default_provider=default_model.provider,
        default_model=default_model.id,
        models=[
            ChatModelOption(
                provider=model.provider,
                id=model.id,
                label=model.label,
                deployment=model.deployment,
            )
            for model in models
        ],
    )
