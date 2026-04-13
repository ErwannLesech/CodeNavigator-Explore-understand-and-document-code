# rag/chatbot.py
import os
import time
from dataclasses import dataclass
from typing import Optional
from mistralai import Mistral
from src.codeNavigator.rag.retriever import Retriever, RetrievedContext
from src.codeNavigator.rag.graph_context import GraphContextProvider
from src.codeNavigator.generation.prompts import RAG_SYSTEM_PROMPT, prompt_rag


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
        model: str = "mistral-large-latest",
    ):
        self.client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        self.model = model
        self.retriever = Retriever(top_k=top_k)
        self.history: list[Message] = []

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
        """Construit l'historique de conversation pour l'API Mistral."""
        messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]

        # Injecter l'historique (fen�tre glissante de 6 derniers �changes)
        for msg in self.history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def chat(
        self,
        query: str,
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
        response = self.client.chat.complete(
            model=self.model,
            messages=messages,  # type: ignore[arg-type]
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

        # 5. Mise à jour de l'historique
        # On stocke la question originale (pas le prompt enrichi) pour garder l'historique lisible
        self.history.append(Message(role="user", content=query))
        self.history.append(Message(role="assistant", content=answer))

        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)

        if prompt_tokens is None and usage is not None:
            prompt_tokens = getattr(usage, "input_tokens", None)
        if completion_tokens is None and usage is not None:
            completion_tokens = getattr(usage, "output_tokens", None)
        if total_tokens is None and prompt_tokens is not None and completion_tokens is not None:
            total_tokens = prompt_tokens + completion_tokens

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
                "model": self.model,
                "duration_ms": elapsed_ms,
                "tokens": {
                    "prompt": prompt_tokens,
                    "completion": completion_tokens,
                    "total": total_tokens,
                },
                "vector_status": vector_status,
                "vector_error": vector_error,
                "retrieval_context": debug_contexts,
                "graph_context": graph_context[:4000] if graph_context else "",
                "prompt_preview": user_prompt[:4000],
            },
        )

    def reset(self):
        self.history.clear()



