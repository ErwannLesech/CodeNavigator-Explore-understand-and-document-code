# embedding/indexer.py
from ingestion.repo_walker import walk_repo
from ingestion.parser_dispatcher import dispatch_parser
from embedding.chunker import chunk_parsed_file, Chunk
from embedding.embedder import Embedder
from embedding.vector_store import VectorStore


def run_indexing(
    repo_path: str,
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
    recreate_collection: bool = False,
    sql_dialect: str = "ansi",
    dry_run: bool = False,  # si True : parse et chunke mais n'appelle pas l'API embedding
) -> list[Chunk]:
    store = VectorStore(host=qdrant_host, port=qdrant_port)
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
