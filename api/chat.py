# api/chat.py
from fastapi import APIRouter
from pydantic import BaseModel
from rag.chatbot import CodeNavigatorChatbot
import os

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Instance partagée — initialisée au démarrage de l'API
_chatbot: CodeNavigatorChatbot = None


def get_chatbot() -> CodeNavigatorChatbot:
    global _chatbot
    if _chatbot is None:
        graph_path = os.getenv("GRAPH_JSON_PATH", "data/output/graph/graph.json")
        _chatbot = CodeNavigatorChatbot(graph_json_path=graph_path)
    return _chatbot


class ChatRequest(BaseModel):
    query: str
    filter_language: str = None
    filter_type: str = None
    filter_file: str = None


class ChatResponseDTO(BaseModel):
    answer: str
    sources: list[dict]
    graph_context_used: bool


@router.post("", response_model=ChatResponseDTO)
def chat(request: ChatRequest):
    bot = get_chatbot()
    response = bot.chat(
        query=request.query,
        filter_language=request.filter_language,
        filter_type=request.filter_type,
        filter_file=request.filter_file,
    )
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
    )


@router.delete("/reset")
def reset_chat():
    get_chatbot().reset()
    return {"status": "ok"}

