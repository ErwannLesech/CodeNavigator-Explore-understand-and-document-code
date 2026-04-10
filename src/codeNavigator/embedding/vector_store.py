# embedding/vector_store.py
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from src.codeNavigator.embedding.chunker import Chunk
import uuid
from typing import Any, Iterable, Optional, cast


COLLECTION_NAME = "CodeNavigatorChunks"
VECTOR_SIZE = 1024  # text-embedding-3-small
# 3072 si tu utilises text-embedding-3-large


class VectorStore:
    def __init__(self, host: str = "localhost", port: int = 6333):
        self.client = QdrantClient(host=host, port=port)

    def create_collection(self, recreate: bool = False):
        existing = [c.name for c in self.client.get_collections().collections]

        if COLLECTION_NAME in existing:
            if recreate:
                self.client.delete_collection(COLLECTION_NAME)
            else:
                return  # d�j� existante, on ne touche pas

        self.client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

    def upsert_chunks(self, chunks: list[Chunk], embeddings: list[list[float]]):
        """Ins�re ou met � jour des chunks avec leurs embeddings."""
        assert len(chunks) == len(embeddings)

        points = [
            PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, chunk.chunk_id)),
                vector=embedding,
                payload={
                    "chunk_id": chunk.chunk_id,
                    "content": chunk.content,
                    "chunk_type": chunk.chunk_type,
                    "language": chunk.language,
                    "source_file": chunk.source_file,
                    "start_line": chunk.start_line,
                    **chunk.metadata,
                },
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        self.client.upsert(collection_name=COLLECTION_NAME, points=points)

    def search(
        self,
        query_vector: list[float],
        top_k: int = 5,
        filter_language: Optional[str] = None,
        filter_type: Optional[str] = None,
        filter_file: Optional[str] = None,
    ) -> list[dict]:
        """Recherche s�mantique avec filtres optionnels sur les m�tadonn�es."""
        must_conditions = []

        if filter_language:
            must_conditions.append(
                FieldCondition(key="language", match=MatchValue(value=filter_language))
            )
        if filter_type:
            must_conditions.append(
                FieldCondition(key="chunk_type", match=MatchValue(value=filter_type))
            )
        if filter_file:
            must_conditions.append(
                FieldCondition(key="source_file", match=MatchValue(value=filter_file))
            )

        query_filter = Filter(must=must_conditions) if must_conditions else None

        # qdrant-client >= 1.10 uses `query_points`; older versions expose `search`.
        search_fn = getattr(self.client, "search", None)
        if callable(search_fn):
            raw_results = search_fn(
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )
            results = list(cast(Iterable[Any], raw_results))
        else:
            query_result = self.client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                limit=top_k,
                query_filter=query_filter,
                with_payload=True,
            )
            results = list(query_result.points)

        formatted_results = []
        for r in results:
            payload = r.payload or {}
            formatted_results.append(
                {
                    "score": r.score,
                    "content": payload.get("content"),
                    "chunk_type": payload.get("chunk_type"),
                    "source_file": payload.get("source_file"),
                    "chunk_id": payload.get("chunk_id"),
                    **{
                        k: v
                        for k, v in payload.items()
                        if k not in ("content", "chunk_type", "source_file", "chunk_id")
                    },
                }
            )

        return formatted_results



