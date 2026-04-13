# backend/chat.py
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from src.codeNavigator.rag.chatbot import CodeNavigatorChatbot
import os
from typing import Optional

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Shared instance initialized at API startup.
_chatbot: Optional[CodeNavigatorChatbot] = None


def get_chatbot() -> CodeNavigatorChatbot:
    global _chatbot
    if _chatbot is None:
        if not os.getenv("MISTRAL_API_KEY"):
            raise RuntimeError("MISTRAL_API_KEY is missing on the backend process")
        graph_path = os.getenv("GRAPH_JSON_PATH", "data/output/graph/graph.json")
        _chatbot = CodeNavigatorChatbot(graph_json_path=graph_path)
    return _chatbot


class ChatRequest(BaseModel):
    query: str
    filter_language: Optional[str] = None
    filter_type: Optional[str] = None
    filter_file: Optional[str] = None


class ChatResponseDTO(BaseModel):
    answer: str
    sources: list[dict]
    graph_context_used: bool
    debug: dict


class ResetResponseDTO(BaseModel):
    status: str


@router.post("", response_model=ChatResponseDTO)
def chat(request: ChatRequest):
    try:
        bot = get_chatbot()
        response = bot.chat(
            query=request.query,
            filter_language=request.filter_language,
            filter_type=request.filter_type,
            filter_file=request.filter_file,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chat backend error: {exc}",
        ) from exc

    return ChatResponseDTO(
        answer=response.answer,
        sources=[
            {
                "source_file": s.source_file,
                "chunk_type": s.chunk_type,
                "score": round(s.score, 3),
                "chunk_id": s.chunk_id,
            }
            for s in response.sources
        ],
        graph_context_used=response.graph_context_used,
        debug=response.debug,
    )


@router.delete("/reset", response_model=ResetResponseDTO)
def reset_chat():
    get_chatbot().reset()
    return ResetResponseDTO(status="ok")
