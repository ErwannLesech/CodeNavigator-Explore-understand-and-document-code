# rag/chatbot.py
import time
from dataclasses import dataclass
from typing import Optional

from src.generation.prompts import RAG_SYSTEM_PROMPT, prompt_rag
from src.rag.graph_context import GraphContextProvider
from src.rag.providers import LLMProvider, ProviderChatResult, get_provider
from src.rag.retriever import RetrievedContext, Retriever


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    answer: str
    sources: list[RetrievedContext]
    graph_context_used: bool
    debug: dict


@dataclass
class PreparedChat:
    provider: LLMProvider
    messages: list[dict[str, str]]
    query: str
    contexts: list[RetrievedContext]
    graph_context: str
    user_prompt: str
    started_at: float
    vector_status: str
    vector_error: str


class CodeNavigatorChatbot:
    def __init__(
        self,
        graph_json_path: Optional[str] = None,
        top_k: int = 6,
        default_model: Optional[str] = None,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        qdrant_collection: str = "CodeNavigatorChunks",
    ):
        self.default_model = default_model
        self.retriever = Retriever(
            top_k=top_k,
            qdrant_host=qdrant_host,
            qdrant_port=qdrant_port,
            qdrant_collection=qdrant_collection,
        )
        self.history: list[Message] = []
        self.qdrant_host = qdrant_host
        self.qdrant_port = qdrant_port
        self.qdrant_collection = qdrant_collection

        self.graph_provider = self._init_graph_provider(graph_json_path)

    def _init_graph_provider(
        self, graph_json_path: Optional[str]
    ) -> Optional[GraphContextProvider]:
        if not graph_json_path:
            return None
        try:
            return GraphContextProvider(graph_json_path)
        except Exception:
            return None  # le graph est optionnel

    def _build_messages(self, user_prompt: str) -> list[dict[str, str]]:
        """Construit l'historique de conversation pour le provider sélectionné."""
        messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]

        for msg in self.history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _select_provider(self, model: Optional[str] = None) -> LLMProvider:
        return get_provider(model or self.default_model)

    def _prepare_chat(
        self,
        query: str,
        filter_language: Optional[str] = None,
        filter_type: Optional[str] = None,
        filter_file: Optional[str] = None,
        model: Optional[str] = None,
    ) -> PreparedChat:
        started_at = time.perf_counter()
        vector_status = "ok"
        vector_error = ""

        try:
            contexts = self.retriever.retrieve(
                query,
                filter_language=filter_language,
                filter_type=filter_type,
                filter_file=filter_file,
            )
        except Exception as exc:
            contexts = []
            vector_status = "unavailable"
            vector_error = str(exc)

        formatted_context = self.retriever.format_context(contexts) if contexts else ""

        graph_context = ""
        if self.graph_provider and contexts:
            graph_context = self.graph_provider.get_context_for_chunks(contexts)
        elif self.graph_provider:
            graph_context = self.graph_provider.get_context_for_query(query)

        user_prompt = prompt_rag(query, formatted_context, graph_context)

        return PreparedChat(
            provider=self._select_provider(model),
            messages=self._build_messages(user_prompt),
            query=query,
            contexts=contexts,
            graph_context=graph_context,
            user_prompt=user_prompt,
            started_at=started_at,
            vector_status=vector_status,
            vector_error=vector_error,
        )

    def _finalize_chat(
        self,
        prepared: PreparedChat,
        answer: str,
        result: ProviderChatResult | None = None,
    ) -> ChatResponse:
        self.history.append(Message(role="user", content=prepared.query))
        self.history.append(Message(role="assistant", content=answer))

        debug_contexts = [
            {
                "source_file": context.source_file,
                "chunk_type": context.chunk_type,
                "chunk_id": context.chunk_id,
                "score": round(context.score, 3),
                "content_excerpt": context.content[:800],
            }
            for context in prepared.contexts
        ]

        elapsed_ms = round((time.perf_counter() - prepared.started_at) * 1000, 1)

        return ChatResponse(
            answer=answer,
            sources=prepared.contexts,
            graph_context_used=bool(prepared.graph_context),
            debug={
                "provider": prepared.provider.provider_name,
                "model": prepared.provider.model_name,
                "duration_ms": elapsed_ms,
                "tokens": {
                    "prompt": result.prompt_tokens if result else None,
                    "completion": result.completion_tokens if result else None,
                    "total": result.total_tokens if result else None,
                },
                "vector_status": prepared.vector_status,
                "vector_error": prepared.vector_error,
                "vector_store": {
                    "host": self.qdrant_host,
                    "port": self.qdrant_port,
                    "collection": self.qdrant_collection,
                },
                "retrieval_context": debug_contexts,
                "graph_context": prepared.graph_context[:4000]
                if prepared.graph_context
                else "",
                "prompt_preview": prepared.user_prompt[:4000],
            },
        )

    def chat(
        self,
        query: str,
        filter_language: Optional[str] = None,
        filter_type: Optional[str] = None,
        filter_file: Optional[str] = None,
        model: Optional[str] = None,
    ) -> ChatResponse:
        prepared = self._prepare_chat(
            query,
            filter_language=filter_language,
            filter_type=filter_type,
            filter_file=filter_file,
            model=model,
        )
        result = prepared.provider.chat(prepared.messages, max_tokens=1500)
        return self._finalize_chat(prepared, result.answer, result)

    def prepare_chat(
        self,
        query: str,
        filter_language: Optional[str] = None,
        filter_type: Optional[str] = None,
        filter_file: Optional[str] = None,
        model: Optional[str] = None,
    ) -> PreparedChat:
        return self._prepare_chat(
            query,
            filter_language=filter_language,
            filter_type=filter_type,
            filter_file=filter_file,
            model=model,
        )

    def complete_chat(
        self,
        prepared: PreparedChat,
        answer: str,
        result: ProviderChatResult | None = None,
    ) -> ChatResponse:
        return self._finalize_chat(prepared, answer, result)

    def reset(self):
        self.history.clear()
