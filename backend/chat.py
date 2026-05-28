# backend/chat.py
import json
import os
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.rag.chatbot import CodeNavigatorChatbot

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Shared instance initialized at API startup.
_chatbot: Optional[CodeNavigatorChatbot] = None


def get_chatbot() -> CodeNavigatorChatbot:
    global _chatbot
    if _chatbot is None:
        graph_path = os.getenv("GRAPH_JSON_PATH", "data/output/graph/graph.json")
        _chatbot = CodeNavigatorChatbot(graph_json_path=graph_path)
    return _chatbot


class ChatRequest(BaseModel):
    query: str
    filter_language: Optional[str] = None
    filter_type: Optional[str] = None
    filter_file: Optional[str] = None
    model: Optional[str] = None


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
            model=request.model,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
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


@router.post("/stream")
def chat_stream(request: ChatRequest):
    bot = get_chatbot()
    try:
        prepared = bot.prepare_chat(
            request.query,
            filter_language=request.filter_language,
            filter_type=request.filter_type,
            filter_file=request.filter_file,
            model=request.model,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc

    def event_stream():
        answer_parts: list[str] = []
        try:
            for delta in prepared.provider.stream_chat(
                prepared.messages, max_tokens=1500
            ):
                answer_parts.append(delta)
                yield json.dumps({"type": "delta", "content": delta}) + "\n"

            response = bot.complete_chat(prepared, "".join(answer_parts))
            yield (
                json.dumps(
                    {
                        "type": "done",
                        "answer": response.answer,
                        "sources": [
                            {
                                "source_file": source.source_file,
                                "chunk_type": source.chunk_type,
                                "score": round(source.score, 3),
                                "chunk_id": source.chunk_id,
                            }
                            for source in response.sources
                        ],
                        "graph_context_used": response.graph_context_used,
                        "debug": response.debug,
                    },
                )
                + "\n"
            )
        except ValueError as exc:
            yield json.dumps({"type": "error", "message": str(exc)}) + "\n"
        except RuntimeError as exc:
            yield json.dumps({"type": "error", "message": str(exc)}) + "\n"
        except Exception as exc:
            yield (
                json.dumps({"type": "error", "message": f"Chat backend error: {exc}"})
                + "\n"
            )

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.delete("/reset", response_model=ResetResponseDTO)
def reset_chat():
    get_chatbot().reset()
    return ResetResponseDTO(status="ok")
