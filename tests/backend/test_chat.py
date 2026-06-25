from types import SimpleNamespace

from fastapi.testclient import TestClient
from mistralai import SDKError

import backend.chat as chat_backend
from backend.app import create_app
from src.rag.chatbot import CodeNavigatorChatbot


class StubChatbot:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def chat(self, **_: object) -> SimpleNamespace:
        if self.error is not None:
            raise self.error

        return SimpleNamespace(
            answer="ok",
            sources=[],
            graph_context_used=False,
            debug={},
        )


def test_chat_returns_503_for_provider_auth_failure(monkeypatch) -> None:
    app = create_app()
    client = TestClient(app)

    def stub_get_chatbot() -> StubChatbot:
        return StubChatbot(
            SDKError(
                message="API error occurred",
                status_code=401,
                body='{"detail":"Unauthorized"}',
            )
        )

    monkeypatch.setattr(chat_backend, "get_chatbot", stub_get_chatbot)

    response = client.post("/api/chat", json={"query": "hello"})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Chat provider authentication failed. Check backend MISTRAL_API_KEY.",
    }


def test_chatbot_uses_qdrant_environment_defaults(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class DummyMistral:
        def __init__(self, api_key: str) -> None:
            captured["api_key"] = api_key

    class DummyRetriever:
        def __init__(
            self,
            top_k: int,
            qdrant_host: str,
            qdrant_port: int,
            qdrant_collection: str,
        ) -> None:
            captured["top_k"] = top_k
            captured["qdrant_host"] = qdrant_host
            captured["qdrant_port"] = qdrant_port
            captured["qdrant_collection"] = qdrant_collection

    monkeypatch.setenv("MISTRAL_API_KEY", "test-key")
    monkeypatch.setenv("QDRANT_HOST", "qdrant")
    monkeypatch.setenv("QDRANT_PORT", "6333")
    monkeypatch.setenv("QDRANT_COLLECTION", "RepoChunks")
    monkeypatch.setattr("src.rag.chatbot.Mistral", DummyMistral)
    monkeypatch.setattr("src.rag.chatbot.Retriever", DummyRetriever)
    monkeypatch.setattr(
        CodeNavigatorChatbot, "_init_graph_provider", lambda self, path: None
    )

    bot = CodeNavigatorChatbot(graph_json_path=None)

    assert captured["api_key"] == "test-key"
    assert captured["top_k"] == 6
    assert captured["qdrant_host"] == "qdrant"
    assert captured["qdrant_port"] == 6333
    assert captured["qdrant_collection"] == "RepoChunks"
    assert bot.qdrant_host == "qdrant"
    assert bot.qdrant_port == 6333
    assert bot.qdrant_collection == "RepoChunks"
