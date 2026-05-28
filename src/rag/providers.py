from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Sequence

from mistralai import Mistral


DEFAULT_MISTRAL_MODEL = "mistral-large-latest"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "llama3.1"


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    id: str
    label: str
    deployment: str


@dataclass(frozen=True)
class ProviderChatResult:
    answer: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class LLMProvider(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int = 1500,
    ) -> ProviderChatResult:
        raise NotImplementedError

    @abstractmethod
    def stream_chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int = 1500,
    ) -> Iterator[str]:
        raise NotImplementedError

    @abstractmethod
    def embed(self, inputs: Sequence[str]) -> list[list[float]]:
        raise NotImplementedError

    @abstractmethod
    def list_models(self) -> list[ModelInfo]:
        raise NotImplementedError


def _build_messages_payload(messages: Sequence[dict[str, str]]) -> list[dict[str, str]]:
    return [dict(message) for message in messages]


def _extract_content_text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(getattr(item, "text", str(item)) for item in content)
    if content is None:
        return ""
    return str(content)


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: dict[str, object] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, object]:
    request_body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(
        url,
        data=request_body,
        headers=request_headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail or f"HTTP {exc.code} on {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Impossible de joindre {url}: {exc.reason}") from exc


def _request_stream_lines(
    url: str,
    *,
    payload: dict[str, object],
    headers: dict[str, str] | None = None,
    timeout: int = 60,
) -> Iterator[str]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if line:
                    yield line
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(detail or f"HTTP {exc.code} on {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Impossible de joindre {url}: {exc.reason}") from exc


def _resolve_total_tokens(
    prompt_tokens: int | None, completion_tokens: int | None
) -> int | None:
    if prompt_tokens is None or completion_tokens is None:
        return None
    return prompt_tokens + completion_tokens


def _mistral_catalog() -> list[ModelInfo]:
    return [
        ModelInfo("mistral", DEFAULT_MISTRAL_MODEL, "Mistral Large", "cloud"),
        ModelInfo("mistral", "mistral-small-latest", "Mistral Small", "cloud"),
        ModelInfo("mistral", "mistral-medium-latest", "Mistral Medium", "cloud"),
    ]


def _openai_catalog() -> list[ModelInfo]:
    return [
        ModelInfo("openai", DEFAULT_OPENAI_MODEL, "GPT-4o mini", "cloud"),
        ModelInfo("openai", "gpt-4.1-mini", "GPT-4.1 mini", "cloud"),
    ]


class MistralProvider(LLMProvider):
    provider_name = "mistral"

    def __init__(self, model_name: str | None = None) -> None:
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise RuntimeError("MISTRAL_API_KEY is missing")
        self.client = Mistral(api_key=api_key)
        self.model_name = model_name or DEFAULT_MISTRAL_MODEL

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int = 1500,
    ) -> ProviderChatResult:
        response = self.client.chat.complete(
            model=self.model_name,
            messages=_build_messages_payload(messages),
            max_tokens=max_tokens,
        )
        if response is None or response.choices is None or not response.choices:
            raise RuntimeError("Mistral API returned an empty response")

        content = response.choices[0].message.content
        usage = getattr(response, "usage", None)
        prompt_tokens = getattr(usage, "prompt_tokens", None)
        completion_tokens = getattr(usage, "completion_tokens", None)
        total_tokens = getattr(usage, "total_tokens", None)
        if prompt_tokens is None and usage is not None:
            prompt_tokens = getattr(usage, "input_tokens", None)
        if completion_tokens is None and usage is not None:
            completion_tokens = getattr(usage, "output_tokens", None)
        if total_tokens is None:
            total_tokens = _resolve_total_tokens(prompt_tokens, completion_tokens)

        return ProviderChatResult(
            answer=_extract_content_text(content),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def stream_chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int = 1500,
    ) -> Iterator[str]:
        stream = self.client.chat.stream(
            model=self.model_name,
            messages=_build_messages_payload(messages),
            max_tokens=max_tokens,
        )
        for event in stream:
            chunk = getattr(event, "data", None)
            choices = getattr(chunk, "choices", None)
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None)
            text = _extract_content_text(content)
            if text:
                yield text

    def embed(self, inputs: Sequence[str]) -> list[list[float]]:
        response = self.client.embeddings.create(
            inputs=list(inputs), model="mistral-embed"
        )
        data = getattr(response, "data", []) or []
        return [list(getattr(item, "embedding", [])) for item in data]

    def list_models(self) -> list[ModelInfo]:
        return _mistral_catalog()


class OpenAIProvider(LLMProvider):
    provider_name = "openai"

    def __init__(self, model_name: str | None = None) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is missing")
        self.api_key = api_key
        self.base_url = os.getenv(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")
        self.model_name = model_name or DEFAULT_OPENAI_MODEL

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_key}"}

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int = 1500,
    ) -> ProviderChatResult:
        data = _request_json(
            f"{self.base_url}/chat/completions",
            method="POST",
            payload={
                "model": self.model_name,
                "messages": _build_messages_payload(messages),
                "max_tokens": max_tokens,
                "stream": False,
            },
            headers=self._headers(),
        )
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("OpenAI API returned an empty response")
        message = choices[0].get("message") or {}
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_tokens")
        completion_tokens = usage.get("completion_tokens")
        total_tokens = usage.get("total_tokens") or _resolve_total_tokens(
            prompt_tokens, completion_tokens
        )
        return ProviderChatResult(
            answer=_extract_content_text(message.get("content")),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def stream_chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int = 1500,
    ) -> Iterator[str]:
        request = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(
                {
                    "model": self.model_name,
                    "messages": _build_messages_payload(messages),
                    "max_tokens": max_tokens,
                    "stream": True,
                },
            ).encode("utf-8"),
            headers={"Content-Type": "application/json", **self._headers()},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line.startswith("data: "):
                        continue
                    payload = line.removeprefix("data: ").strip()
                    if payload == "[DONE]":
                        break
                    data = json.loads(payload)
                    for choice in data.get("choices", []):
                        delta = choice.get("delta") or {}
                        text = _extract_content_text(delta.get("content"))
                        if text:
                            yield text
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(detail or f"HTTP {exc.code} on {self.base_url}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Impossible de joindre {self.base_url}: {exc.reason}"
            ) from exc

    def embed(self, inputs: Sequence[str]) -> list[list[float]]:
        data = _request_json(
            f"{self.base_url}/embeddings",
            method="POST",
            payload={"model": "text-embedding-3-small", "input": list(inputs)},
            headers=self._headers(),
        )
        return [list(item.get("embedding", [])) for item in data.get("data", [])]

    def list_models(self) -> list[ModelInfo]:
        return _openai_catalog()


class OllamaProvider(LLMProvider):
    provider_name = "ollama"

    def __init__(self, model_name: str | None = None) -> None:
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip(
            "/"
        )
        self.model_name = model_name or DEFAULT_OLLAMA_MODEL

    def _chat_url(self) -> str:
        return f"{self.base_url}/api/chat"

    def _tags_url(self) -> str:
        return f"{self.base_url}/api/tags"

    def _available_tags(self) -> list[str]:
        # Try the older /api/tags endpoint first (legacy Ollama API),
        # then fall back to the newer /v1/models shape used by some Ollama versions.
        # Normalize both formats into a simple list of model ids/names.
        # On network error, raise to let caller handle the failure.
        # Try /api/tags
        try:
            data = _request_json(self._tags_url())
            models = data.get("models") or []
            tags: list[str] = []
            for item in models:
                name = item.get("name")
                if isinstance(name, str) and name:
                    tags.append(name)
            if tags:
                return tags
        except RuntimeError:
            # ignore and try fallback
            pass

        # Fallback to /v1/models which returns {"object":"list","data":[{"id":...}, ...]}
        try:
            v1_url = f"{self.base_url}/v1/models"
            data = _request_json(v1_url)
            items = data.get("data") or []
            tags = []
            for item in items:
                # prefer 'id' then 'name'
                mid = item.get("id") or item.get("name")
                if isinstance(mid, str) and mid:
                    tags.append(mid)
            return tags
        except RuntimeError:
            # propagate empty list to caller to indicate no local models found
            return []

    def chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int = 1500,
    ) -> ProviderChatResult:
        data = _request_json(
            self._chat_url(),
            method="POST",
            payload={
                "model": self.model_name,
                "messages": _build_messages_payload(messages),
                "stream": False,
                "options": {"num_predict": max_tokens},
            },
        )
        message = data.get("message") or {}
        usage = data.get("usage") or {}
        prompt_tokens = usage.get("prompt_eval_count")
        completion_tokens = usage.get("eval_count")
        total_tokens = usage.get("total_tokens") or _resolve_total_tokens(
            prompt_tokens, completion_tokens
        )
        return ProviderChatResult(
            answer=_extract_content_text(message.get("content")),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )

    def stream_chat(
        self,
        messages: Sequence[dict[str, str]],
        *,
        max_tokens: int = 1500,
    ) -> Iterator[str]:
        for line in _request_stream_lines(
            self._chat_url(),
            payload={
                "model": self.model_name,
                "messages": _build_messages_payload(messages),
                "stream": True,
                "options": {"num_predict": max_tokens},
            },
        ):
            payload = json.loads(line)
            message = payload.get("message") or {}
            text = _extract_content_text(message.get("content"))
            if text:
                yield text

    def embed(self, inputs: Sequence[str]) -> list[list[float]]:
        data = _request_json(
            f"{self.base_url}/api/embeddings",
            method="POST",
            payload={"model": self.model_name, "prompt": inputs[0] if inputs else ""},
        )
        embedding = data.get("embedding") or []
        return [list(embedding)] if embedding else []

    def list_models(self) -> list[ModelInfo]:
        try:
            tags = self._available_tags()
        except RuntimeError:
            return []
        return [ModelInfo(self.provider_name, tag, tag, "local") for tag in tags]


def list_available_models() -> list[ModelInfo]:
    models: list[ModelInfo] = []

    if os.getenv("MISTRAL_API_KEY"):
        models.extend(_mistral_catalog())

    if os.getenv("OPENAI_API_KEY"):
        models.extend(_openai_catalog())

    models.extend(OllamaProvider().list_models())
    return models


def resolve_default_model(models: list[ModelInfo] | None = None) -> ModelInfo:
    catalog = models if models is not None else list_available_models()
    if not catalog:
        raise RuntimeError("No LLM provider is available")

    requested_default = os.getenv("RAG_DEFAULT_MODEL")
    if requested_default:
        for model in catalog:
            if model.id == requested_default:
                return model

    for provider_name in ("mistral", "openai", "ollama"):
        for model in catalog:
            if model.provider == provider_name:
                return model

    return catalog[0]


def get_provider(model_name: str | None = None) -> LLMProvider:
    available_models = list_available_models()

    if model_name:
        for model in available_models:
            if model.id == model_name:
                if model.provider == "mistral":
                    return MistralProvider(model_name=model.id)
                if model.provider == "openai":
                    return OpenAIProvider(model_name=model.id)
                if model.provider == "ollama":
                    return OllamaProvider(model_name=model.id)

        if model_name in {model.id for model in _mistral_catalog()}:
            return MistralProvider(model_name=model_name)
        if model_name in {model.id for model in _openai_catalog()}:
            return OpenAIProvider(model_name=model_name)

        if os.getenv("OLLAMA_BASE_URL") or any(
            model.provider == "ollama" for model in available_models
        ):
            raise RuntimeError(
                f"Le modele {model_name} est indisponible ou Ollama n'est pas joignable"
            )

        raise ValueError(f"Unknown model: {model_name}")

    default_model = resolve_default_model(available_models)
    if default_model.provider == "mistral":
        return MistralProvider(model_name=default_model.id)
    if default_model.provider == "openai":
        return OpenAIProvider(model_name=default_model.id)
    if default_model.provider == "ollama":
        return OllamaProvider(model_name=default_model.id)

    raise RuntimeError("No LLM provider is available")
