from __future__ import annotations

import os

from src.embedding.vector_store import VectorStore

from backend.schemas import QdrantInfoResponse


def qdrant_url() -> str:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    return f"http://{host}:{port}/dashboard"


def qdrant_public_url() -> str:
    host = os.getenv("QDRANT_PUBLIC_HOST", "localhost")
    port = int(os.getenv("QDRANT_PUBLIC_PORT", os.getenv("QDRANT_PORT", "6333")))
    return f"http://{host}:{port}/dashboard"


def qdrant_info() -> QdrantInfoResponse:
    host = os.getenv("QDRANT_HOST", "localhost")
    port = int(os.getenv("QDRANT_PORT", "6333"))
    url = qdrant_public_url()
    store = VectorStore(host=host, port=port)
    collections = [item.name for item in store.client.get_collections().collections]

    return QdrantInfoResponse(
        host=host,
        port=port,
        url=url,
        reachable=True,
        active_collection="CodeNavigatorChunks",
        collections=collections,
    )
