from __future__ import annotations

import json
import os
from typing import Literal
from urllib import error, request

LLMProvider = Literal["mistral", "ollama"]

DEFAULT_MISTRAL_CHAT_MODEL = os.getenv("MISTRAL_CHAT_MODEL", "mistral-large-latest")
DEFAULT_MISTRAL_EMBEDDING_MODEL = os.getenv("MISTRAL_EMBEDDING_MODEL", "mistral-embed")
DEFAULT_OLLAMA_CHAT_MODEL = os.getenv("OLLAMA_CHAT_MODEL", "llama3.1:8b")
DEFAULT_OLLAMA_EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "nomic-embed-text")
DEFAULT_OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _candidate_ollama_base_urls() -> list[str]:
    configured = os.getenv("OLLAMA_BASE_URL", "").strip()
    candidates = [
        configured,
        DEFAULT_OLLAMA_BASE_URL,
        "http://host.docker.internal:11434",
        "http://ollama:11434",
        "http://localhost:11434",
    ]
    normalized: list[str] = []
    for url in candidates:
        if not url:
            continue
        clean = url.rstrip("/")
        if clean not in normalized:
            normalized.append(clean)
    return normalized


def _normalize_provider(
    provider: str | None, default: LLMProvider = "mistral"
) -> LLMProvider:
    value = (provider or "").strip().lower()
    if value in ("ollama", "mistral"):
        return value
    return default


def resolve_chat_provider(provider: str | None = None) -> LLMProvider:
    return _normalize_provider(
        provider, default=_normalize_provider(os.getenv("CHAT_PROVIDER"))
    )


def resolve_embedding_provider(provider: str | None = None) -> LLMProvider:
    return _normalize_provider(
        provider,
        default=_normalize_provider(os.getenv("EMBEDDING_PROVIDER")),
    )


def resolve_chat_model(provider: str | None, model: str | None) -> str:
    clean_model = (model or "").strip()
    if clean_model:
        return clean_model

    if resolve_chat_provider(provider) == "ollama":
        return DEFAULT_OLLAMA_CHAT_MODEL
    return DEFAULT_MISTRAL_CHAT_MODEL


def resolve_embedding_model(provider: str | None, model: str | None) -> str:
    clean_model = (model or "").strip()
    if clean_model:
        return clean_model

    if resolve_embedding_provider(provider) == "ollama":
        return DEFAULT_OLLAMA_EMBEDDING_MODEL
    return DEFAULT_MISTRAL_EMBEDDING_MODEL


def _fetch_ollama_tags(base_url: str) -> list[str]:
    url = f"{base_url.rstrip('/')}/api/tags"
    req = request.Request(url, method="GET")

    try:
        with request.urlopen(req, timeout=3.0) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (error.URLError, error.HTTPError, TimeoutError, json.JSONDecodeError):
        return []

    models = payload.get("models")
    if not isinstance(models, list):
        return []

    names: list[str] = []
    for item in models:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            names.append(name.strip())
    return names


def discover_ollama_models() -> tuple[list[str], str]:
    for base_url in _candidate_ollama_base_urls():
        models = _fetch_ollama_tags(base_url)
        if models:
            return models, base_url
    return [], _candidate_ollama_base_urls()[0] if _candidate_ollama_base_urls() else ""


def list_available_chat_models() -> dict[str, object]:
    ollama_models, ollama_base_url = discover_ollama_models()
    models: list[dict[str, str]] = [
        {
            "provider": "mistral",
            "id": DEFAULT_MISTRAL_CHAT_MODEL,
            "label": f"Mistral ({DEFAULT_MISTRAL_CHAT_MODEL})",
            "deployment": "cloud",
        }
    ]

    for model in ollama_models:
        models.append(
            {
                "provider": "ollama",
                "id": model,
                "label": f"Ollama ({model})",
                "deployment": "local",
            }
        )

    default_provider = resolve_chat_provider(None)
    default_model = resolve_chat_model(default_provider, None)

    return {
        "default_provider": default_provider,
        "default_model": default_model,
        "ollama_base_url": ollama_base_url,
        "ollama_reachable": len(ollama_models) > 0,
        "models": models,
    }
