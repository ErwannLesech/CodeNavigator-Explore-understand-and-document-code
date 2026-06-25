from fastapi import APIRouter, status

from src.llm.providers import list_available_chat_models

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models", status_code=status.HTTP_200_OK)
async def get_models() -> dict:
    return list_available_chat_models()
