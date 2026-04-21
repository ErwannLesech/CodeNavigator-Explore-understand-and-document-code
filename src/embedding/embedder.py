# embedding/embedder.py
import os
import time
from mistralai import Mistral
from src.embedding.chunker import Chunk
import dotenv

dotenv.load_dotenv()  # charge les variables d'environnement depuis le fichier .env

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

    def embed_chunks(self, chunks: list[Chunk]) -> list[list[float]]:
        """Génére les embeddings par batch pour éviter les rate limits."""
        all_embeddings = []

        for i in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[i : i + BATCH_SIZE]
            texts = [c.content for c in batch]
            response = self.client.embeddings.create(
                model=EMBEDDING_MODEL, inputs=texts
            )
            if response is None or response.data is None:
                raise RuntimeError("Embedding API returned an empty response")
            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

            # Rate limit basique entre les batches
            if i + BATCH_SIZE < len(chunks):
                time.sleep(0.5)
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """Embed une requéte utilisateur pour la recherche."""
        response = self.client.embeddings.create(model=EMBEDDING_MODEL, inputs=[query])
        if response is None or response.data is None or not response.data:
            raise RuntimeError("Embedding API returned an empty response")
        embedding = response.data[0].embedding
        if embedding is None:
            raise RuntimeError("Embedding API returned an empty vector")
        return embedding
