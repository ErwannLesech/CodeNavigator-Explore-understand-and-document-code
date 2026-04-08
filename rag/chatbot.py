# rag/chatbot.py
import os
from dataclasses import dataclass
from mistralai import Mistral
from rag.retriever import Retriever, RetrievedContext
from rag.graph_context import GraphContextProvider
from generation.prompts import RAG_SYSTEM_PROMPT, prompt_rag


@dataclass
class Message:
    role: str  # "user" | "assistant"
    content: str


@dataclass
class ChatResponse:
    answer: str
    sources: list[RetrievedContext]
    graph_context_used: bool


class CodeNavigatorChatbot:
    def __init__(
        self,
        graph_json_path: str = None,
        top_k: int = 6,
        model: str = "mistral-large-latest",
    ):
        self.client = Mistral(api_key=os.environ["MISTRAL_API_KEY"])
        self.model = model
        self.retriever = Retriever(top_k=top_k)
        self.history: list[Message] = []

        self.graph_provider = None
        if graph_json_path:
            try:
                self.graph_provider = GraphContextProvider(graph_json_path)
            except Exception:
                pass  # graph optionnel, ne bloque pas le chatbot

    def _build_messages(self, user_prompt: str) -> list[dict]:
        """Construit l'historique de conversation pour l'API Mistral."""
        messages = [{"role": "system", "content": RAG_SYSTEM_PROMPT}]

        # Injecter l'historique (fenêtre glissante de 6 derniers échanges)
        for msg in self.history[-6:]:
            messages.append({"role": msg.role, "content": msg.content})

        messages.append({"role": "user", "content": user_prompt})
        return messages

    def chat(
        self,
        query: str,
        filter_language: str = None,
        filter_type: str = None,
        filter_file: str = None,
    ) -> ChatResponse:

        # 1. Retrieval
        contexts = self.retriever.retrieve(
            query,
            filter_language=filter_language,
            filter_type=filter_type,
            filter_file=filter_file,
        )
        formatted_context = self.retriever.format_context(contexts)

        # 2. Graph context
        graph_context = ""
        if self.graph_provider and contexts:
            graph_context = self.graph_provider.get_context_for_chunks(contexts)

        # 3. Construction du prompt RAG
        user_prompt = prompt_rag(query, formatted_context, graph_context)

        # 4. Appel LLM avec historique
        messages = self._build_messages(user_prompt)
        response = self.client.chat.complete(
            model=self.model,
            messages=messages,
            max_tokens=1500,
        )
        answer = response.choices[0].message.content

        # 5. Mise à jour de l'historique
        # On stocke la question originale (pas le prompt enrichi) pour garder l'historique lisible
        self.history.append(Message(role="user", content=query))
        self.history.append(Message(role="assistant", content=answer))

        return ChatResponse(
            answer=answer, sources=contexts, graph_context_used=bool(graph_context)
        )

    def reset(self):
        self.history.clear()
