# embedding/indexer.py
from src.ingestion.repo_walker import walk_repo
from src.ingestion.parser_dispatcher import dispatch_parser
from src.embedding.chunker import chunk_parsed_file, Chunk
from src.embedding.embedder import Embedder
from src.embedding.vector_store import VectorStore


def run_indexing(
    repo_path: str,
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
    qdrant_collection: str = "CodeNavigatorChunks",
    recreate_collection: bool = False,
    sql_dialect: str = "ansi",
    dry_run: bool = False,  # si True : parse et chunke mais n'appelle pas l'API embedding
) -> list[Chunk]:
    store = VectorStore(
        host=qdrant_host, port=qdrant_port, collection_name=qdrant_collection
    )
    store.create_collection(recreate=recreate_collection)

    embedder = Embedder() if not dry_run else None

    files = list(walk_repo(repo_path))
    all_chunks: list[Chunk] = []

    for source_file in files:
        parsed = dispatch_parser(source_file, sql_dialect=sql_dialect)
        chunks = chunk_parsed_file(parsed)
        all_chunks.extend(chunks)

    if dry_run:
        return all_chunks

    if embedder is None:
        raise RuntimeError("Embedder is not initialized")

    embeddings = embedder.embed_chunks(all_chunks)
    store.upsert_chunks(all_chunks, embeddings)
    return all_chunks
