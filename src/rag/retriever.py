# rag/retriever.py
from dataclasses import dataclass
from typing import Optional
from src.embedding.embedder import Embedder
from src.embedding.vector_store import VectorStore


@dataclass
class RetrievedContext:
    content: str
    chunk_type: str
    source_file: str
    chunk_id: str
    score: float
    metadata: dict


class Retriever:
    def __init__(
        self,
        top_k: int = 6,
        qdrant_host: str = "localhost",
        qdrant_port: int = 6333,
        qdrant_collection: str = "CodeNavigatorChunks",
    ):
        self.embedder = Embedder()
        self.store = VectorStore(
            host=qdrant_host,
            port=qdrant_port,
            collection_name=qdrant_collection,
        )
        self.top_k = top_k

    def retrieve(
        self,
        query: str,
        filter_language: Optional[str] = None,
        filter_type: Optional[str] = None,
        filter_file: Optional[str] = None,
    ) -> list[RetrievedContext]:
        query_vector = self.embedder.embed_query(query)

        results = self.store.search(
            query_vector=query_vector,
            top_k=self.top_k,
            filter_language=filter_language,
            filter_type=filter_type,
            filter_file=filter_file,
        )

        return [
            RetrievedContext(
                content=r["content"],
                chunk_type=r["chunk_type"],
                source_file=r["source_file"],
                chunk_id=r["chunk_id"],
                score=r["score"],
                metadata={
                    k: v
                    for k, v in r.items()
                    if k
                    not in ("content", "chunk_type", "source_file", "chunk_id", "score")
                },
            )
            for r in results
        ]

    def format_context(self, contexts: list[RetrievedContext]) -> str:
        """Formate les chunks récupérés en bloc de contexte pour le prompt."""
        parts = []
        for i, ctx in enumerate(contexts, 1):
            parts.append(
                f"[Source {i}] {ctx.source_file} ({ctx.chunk_type})\n{ctx.content}"
            )
        return "\n\n---\n\n".join(parts)
