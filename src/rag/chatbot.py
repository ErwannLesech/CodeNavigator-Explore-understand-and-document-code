import json
import os
import time
from dataclasses import dataclass
from typing import Optional
from urllib import error, request

from mistralai import Mistral

from src.generation.prompts import RAG_SYSTEM_PROMPT, prompt_rag
from src.llm.providers import (
    DEFAULT_OLLAMA_BASE_URL,
    resolve_chat_model,
    resolve_chat_provider,
)
from src.rag.graph_context import GraphContextProvider
from src.rag.retriever import Retriever, RetrievedContext


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


class CodeNavigatorChatbot:
    def __init__(
        self,
        graph_json_path: Optional[str] = None,
        top_k: int = 6,
        model: str | None = None,
        provider: str | None = None,
        embedding_provider: str | None = None,
        embedding_model: str | None = None,
        ollama_base_url: str | None = None,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        qdrant_collection: str = "CodeNavigatorChunks",
    ):
        self.provider = resolve_chat_provider(provider)
        self.model = resolve_chat_model(self.provider, model)
        self.ollama_base_url = (ollama_base_url or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        self.client: Mistral | None = None
        if self.provider == "mistral":
            api_key = os.getenv("MISTRAL_API_KEY")
            if not api_key:
                raise RuntimeError("MISTRAL_API_KEY is missing on the backend process")
            self.client = Mistral(api_key=api_key)
        self.retriever = Retriever(
            top_k=top_k,
            qdrant_host=qdrant_host,
            qdrant_port=qdrant_port,
            qdrant_collection=qdrant_collection,
            embedding_provider=embedding_provider,
            embedding_model=embedding_model,
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
        messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]

        # Injecter l'historique (fenétre glissante de 6 derniers échanges)
        for msg in self.history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def _chat_with_mistral(
        self, model: str, messages: list[dict[str, str]]
    ) -> tuple[str, dict[str, int | None]]:
        if self.client is None:
            api_key = os.getenv("MISTRAL_API_KEY")
            if not api_key:
                raise RuntimeError("MISTRAL_API_KEY is missing on the backend process")
            self.client = Mistral(api_key=api_key)

        response = self.client.chat.complete(
            model=model,
            messages=messages,
            max_tokens=1500,
        )
        if response is None or response.choices is None or not response.choices:
            raise RuntimeError("LLM API returned an empty response")

        content = response.choices[0].message.content
        if isinstance(content, str):
            answer = content
        elif isinstance(content, list):
            answer = "\n".join(getattr(item, "text", str(item)) for item in content)
        elif content is None:
            raise RuntimeError("LLM API returned empty content")
        else:
            answer = str(content)

        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)

        if prompt_tokens is None and usage is not None:
            prompt_tokens = getattr(usage, "input_tokens", None)
        if completion_tokens is None and usage is not None:
            completion_tokens = getattr(usage, "output_tokens", None)
        if (
            total_tokens is None
            and prompt_tokens is not None
            and completion_tokens is not None
        ):
            total_tokens = prompt_tokens + completion_tokens

        return answer, {
            "prompt": prompt_tokens,
            "completion": completion_tokens,
            "total": total_tokens,
        }

    def _chat_with_ollama(
        self, model: str, messages: list[dict[str, str]]
    ) -> tuple[str, dict[str, int | None]]:
        req = request.Request(
            f"{self.ollama_base_url}/api/chat",
            data=json.dumps(
                {"model": model, "messages": messages, "stream": False}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=60.0) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (
            error.URLError,
            error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

        message = payload.get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Ollama API returned an invalid response")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Ollama API returned empty content")

        prompt_tokens = payload.get("prompt_eval_count")
        completion_tokens = payload.get("eval_count")
        total_tokens = None
        if isinstance(prompt_tokens, int) and isinstance(completion_tokens, int):
            total_tokens = prompt_tokens + completion_tokens

        return content, {
            "prompt": prompt_tokens if isinstance(prompt_tokens, int) else None,
            "completion": completion_tokens
            if isinstance(completion_tokens, int)
            else None,
            "total": total_tokens,
        }

    def chat(
        self,
        query: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        filter_language: Optional[str] = None,
        filter_type: Optional[str] = None,
        filter_file: Optional[str] = None,
    ) -> ChatResponse:
        started_at = time.perf_counter()
        vector_status = "ok"
        vector_error = ""

        # 1. Retrieval
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

        # 2. Graph context
        graph_context = ""
        if self.graph_provider and contexts:
            graph_context = self.graph_provider.get_context_for_chunks(contexts)
        elif self.graph_provider:
            graph_context = self.graph_provider.get_context_for_query(query)

        # 3. Construction du prompt RAG
        user_prompt = prompt_rag(query, formatted_context, graph_context)

        # 4. Appel LLM avec historique
        messages = self._build_messages(user_prompt)
        selected_provider = resolve_chat_provider(provider or self.provider)
        selected_model = resolve_chat_model(selected_provider, model or self.model)
        if selected_provider == "ollama":
            answer, tokens = self._chat_with_ollama(selected_model, messages)
        else:
            answer, tokens = self._chat_with_mistral(selected_model, messages)

        # 5. Mise à jour de l'historique
        # On stocke la question originale (pas le prompt enrichi) pour garder l'historique lisible
        self.history.append(Message(role="user", content=query))
        self.history.append(Message(role="assistant", content=answer))

        debug_contexts = [
            {
                "source_file": c.source_file,
                "chunk_type": c.chunk_type,
                "chunk_id": c.chunk_id,
                "score": round(c.score, 3),
                "content_excerpt": c.content[:800],
            }
            for c in contexts
        ]

        elapsed_ms = round((time.perf_counter() - started_at) * 1000, 1)

        return ChatResponse(
            answer=answer,
            sources=contexts,
            graph_context_used=bool(graph_context),
            debug={
                "provider": selected_provider,
                "model": selected_model,
                "duration_ms": elapsed_ms,
                "tokens": tokens,
                "vector_status": vector_status,
                "vector_error": vector_error,
                "vector_store": {
                    "host": self.qdrant_host,
                    "port": self.qdrant_port,
                    "collection": self.qdrant_collection,
                },
                "retrieval_context": debug_contexts,
                "graph_context": graph_context[:4000] if graph_context else "",
                "prompt_preview": user_prompt[:4000],
            },
        )

    def reset(self):
        self.history.clear()
