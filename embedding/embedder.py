# embedding/embedder.py
import os
import time
import logging
from mistralai import Mistral
from embedding.chunker import Chunk
import dotenv

dotenv.load_dotenv()  # charge les variables d'environnement depuis le fichier .env

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "mistral-embed"
BATCH_SIZE = 100


class Embedder:
    def __init__(self):
        api_key = os.getenv("MISTRAL_API_KEY")
        if not api_key:
            raise ValueError(
                "MISTRAL_API_KEY environment variable is not set. "
                "Please set it before running: export MISTRAL_API_KEY='...'"
            )
        self.client = Mistral(api_key=api_key)
        logger.info(f"Embedder initialized with model: {EMBEDDING_MODEL}")

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        """Génère les embeddings par batch pour éviter les rate limits."""
        all_embeddings = []
        logger.info(f"Starting embedding generation for {len(chunks)} chunks...")

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            texts = [c.content for c in batch]
            batch_num = (i // BATCH_SIZE) + 1
            total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE

            try:
                logger.debug(
                    f"Embedding batch {batch_num}/{total_batches} ({len(texts)} texts)..."
                )
                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL, inputs=texts
                )
                batch_embeddings = [item.embedding for item in response.data]
                all_embeddings.extend(batch_embeddings)
                logger.debug(
                    f"Batch {batch_num}/{total_batches} completed successfully"
                )

            except Exception as e:
                logger.error(
                    f"Error embedding batch {batch_num}/{total_batches}: {e}",
                    exc_info=True,
                )
                raise

            # Rate limit basique entre les batches
            if i + BATCH_SIZE < len(chunks):
                time.sleep(0.5)

        logger.info(
            f"Embedding generation completed: {len(all_embeddings)} embeddings generated"
        )
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """Embed une requête utilisateur pour la recherche."""
        response = self.client.embeddings.create(model=EMBEDDING_MODEL, inputs=[query])
        return response.data[0].embedding
