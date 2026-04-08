# embedding/indexer.py
import logging
from rich.progress import track
from rich import print

from ingestion.repo_walker import walk_repo
from ingestion.parser_dispatcher import dispatch_parser
from embedding.chunker import chunk_parsed_file, Chunk
from embedding.embedder import Embedder
from embedding.vector_store import VectorStore

logger = logging.getLogger(__name__)


def run_indexing(
    repo_path: str,
    qdrant_host: str = "localhost",
    qdrant_port: int = 6333,
    recreate_collection: bool = False,
    sql_dialect: str = "ansi",
    dry_run: bool = False,  # si True : parse et chunke mais n'appelle pas l'API embedding
) -> list[Chunk]:
    try:
        logger.info(f"Starting indexing: repo_path={repo_path}, dry_run={dry_run}")

        store = VectorStore(host=qdrant_host, port=qdrant_port)
        store.create_collection(recreate=recreate_collection)
        logger.info(f"Vector store initialized at {qdrant_host}:{qdrant_port}")

        embedder = Embedder() if not dry_run else None

        # Etape 1 : ingestion
        logger.info("Starting repository walk...")
        files = list(walk_repo(repo_path))
        print(f"[blue]{len(files)} fichiers detectes[/blue]")
        logger.info(f"Ingestion terminee : {len(files)} fichiers traites")

        all_chunks: list[Chunk] = []

        for idx, source_file in enumerate(track(files, description="Parsing..."), 1):
            try:
                logger.debug(
                    f"[{idx}/{len(files)}] Dispatching parser for {source_file.relative_path}"
                )
                parsed = dispatch_parser(source_file, sql_dialect=sql_dialect)
                logger.debug(f"[{idx}/{len(files)}] Dispatch complete, now chunking...")
                chunks = chunk_parsed_file(parsed)
                logger.debug(
                    f"[{idx}/{len(files)}] Got {len(chunks)} chunks from {source_file.relative_path}"
                )
                all_chunks.extend(chunks)
            except Exception as e:
                logger.error(
                    f"Error processing file {source_file.relative_path}: {e}",
                    exc_info=True,
                )
                raise

        print(f"[blue]{len(all_chunks)} chunks generes[/blue]")
        logger.info(f"Parsing completed: {len(all_chunks)} chunks generated")

        if dry_run:
            print("[yellow]dry_run=True : embedding et indexation ignores[/yellow]")
            logger.info("Dry-run mode: skipping embedding and indexation")
            for c in all_chunks[:5]:
                print(f"  [{c.chunk_type}] {c.chunk_id}")
                print(f"  {c.content[:200]}\n")
            return all_chunks

        # Etape 2 : embedding
        print("[blue]Generation des embeddings...[/blue]")
        logger.info("Starting embedding generation...")
        embeddings = embedder.embed_chunks(all_chunks)
        logger.info(f"Embedding completed: {len(embeddings)} embeddings generated")

        # Etape 3 : indexation Qdrant
        print("[blue]Indexation dans Qdrant...[/blue]")
        logger.info("Starting Qdrant indexation...")
        store.upsert_chunks(all_chunks, embeddings)
        logger.info(f"Qdrant indexation completed: {len(all_chunks)} chunks indexed")

        print(f"[green]{len(all_chunks)} chunks indexes avec succes[/green]")
        return all_chunks

    except Exception as e:
        logger.error(f"Error during indexing: {e}", exc_info=True)
        print(f"[red]ERROR: {e}[/red]")
        raise
