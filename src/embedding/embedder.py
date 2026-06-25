import json
import os
import time
from typing import Callable
from urllib import error, request

import dotenv
from mistralai import Mistral

from src.embedding.chunker import Chunk
from src.llm.providers import (
    DEFAULT_OLLAMA_BASE_URL,
    resolve_embedding_model,
    resolve_embedding_provider,
)

dotenv.load_dotenv()

BATCH_SIZE = 100


class Embedder:
    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        ollama_base_url: str | None = None,
    ):
        self.provider = resolve_embedding_provider(provider)
        self.model = resolve_embedding_model(self.provider, model)
        self.ollama_base_url = (ollama_base_url or DEFAULT_OLLAMA_BASE_URL).rstrip("/")
        self.vector_size: int | None = None

        self.client: Mistral | None = None
        if self.provider == "mistral":
            api_key = os.getenv("MISTRAL_API_KEY")
            if not api_key:
                raise ValueError(
                    "MISTRAL_API_KEY environment variable is not set. "
                    "Please set it before running: export MISTRAL_API_KEY='...'"
                )
            self.client = Mistral(api_key=api_key)

    def _set_vector_size(self, embeddings: list[list[float]]) -> None:
        if embeddings and embeddings[0]:
            self.vector_size = len(embeddings[0])

    def _ollama_request(self, path: str, payload: dict) -> dict:
        req = request.Request(
            f"{self.ollama_base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=30.0) as response:
                return json.loads(response.read().decode("utf-8"))
        except (
            error.URLError,
            error.HTTPError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(f"Ollama request failed: {exc}") from exc

    def _embed_chunks_mistral(self, texts: list[str]) -> list[list[float]]:
        if self.client is None:
            raise RuntimeError("Mistral client is not initialized")
        response = self.client.embeddings.create(model=self.model, inputs=texts)
        if response is None or response.data is None:
            raise RuntimeError("Embedding API returned an empty response")
        return [item.embedding for item in response.data if item.embedding is not None]

    def _embed_chunks_ollama(self, texts: list[str]) -> list[list[float]]:
        payload = self._ollama_request(
            "/api/embed",
            {"model": self.model, "input": texts},
        )
        values = payload.get("embeddings")
        if not isinstance(values, list):
            raise RuntimeError("Ollama embedding API returned an invalid response")
        embeddings = [v for v in values if isinstance(v, list)]
        if len(embeddings) != len(texts):
            raise RuntimeError(
                "Ollama embedding API returned unexpected number of vectors"
            )
        return embeddings

    def embed_chunks(
        self,
        chunks: list[Chunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[list[float]]:
        all_embeddings: list[list[float]] = []
        total = len(chunks)

        for i in range(0, total, BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            texts = [c.content for c in batch]
            if self.provider == "ollama":
                batch_embeddings = self._embed_chunks_ollama(texts)
            else:
                batch_embeddings = self._embed_chunks_mistral(texts)
            all_embeddings.extend(batch_embeddings)

            done = min(i + BATCH_SIZE, total)
            if progress_callback is not None:
                progress_callback(done, total)

            if i + BATCH_SIZE < total:
                time.sleep(0.2 if self.provider == "ollama" else 0.5)

        self._set_vector_size(all_embeddings)
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        if self.provider == "ollama":
            payload = self._ollama_request(
                "/api/embed",
                {"model": self.model, "input": [query]},
            )
            vectors = payload.get("embeddings")
            if (
                not isinstance(vectors, list)
                or not vectors
                or not isinstance(vectors[0], list)
            ):
                raise RuntimeError("Ollama embedding API returned an empty response")
            embedding = vectors[0]
            self.vector_size = len(embedding)
            return embedding

        if self.client is None:
            raise RuntimeError("Mistral client is not initialized")
        response = self.client.embeddings.create(model=self.model, inputs=[query])
        if response is None or response.data is None or not response.data:
            raise RuntimeError("Embedding API returned an empty response")
        embedding = response.data[0].embedding
        if embedding is None:
            raise RuntimeError("Embedding API returned an empty vector")
        self.vector_size = len(embedding)
        return embedding
