"""
OpenAI Embedding Client

Generates text embeddings using OpenAI's text-embedding-3-small model.
"""
from typing import List
from openai import AsyncOpenAI
from loguru import logger
from domain.exceptions import EmbeddingServiceError


class OpenAIEmbeddingClient:
    """
    OpenAI embedding client for vector generation

    Uses text-embedding-3-small model (1536 dimensions)
    for generating text embeddings for RAG retrieval.
    """

    MODEL = "text-embedding-3-small"
    DIMENSIONS = 1536

    def __init__(self, api_key: str):
        """
        Initialize OpenAI embedding client

        Args:
            api_key: OpenAI API key
        """
        self._client = AsyncOpenAI(api_key=api_key)

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to generate embedding for

        Returns:
            List of floats (1536 dimensions)

        Raises:
            EmbeddingServiceError: If embedding generation fails
        """
        try:
            response = await self._client.embeddings.create(
                model=self.MODEL,
                input=text,
                dimensions=self.DIMENSIONS
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(f"Embedding generation failed: {e}")
            raise EmbeddingServiceError(f"Failed to generate embedding: {e}") from e

    async def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of texts to generate embeddings for

        Returns:
            List of embedding vectors (each 1536 dimensions)

        Raises:
            EmbeddingServiceError: If embedding generation fails
        """
        if not texts:
            return []

        try:
            response = await self._client.embeddings.create(
                model=self.MODEL,
                input=texts,
                dimensions=self.DIMENSIONS
            )
            # Sort by index to maintain order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]

        except Exception as e:
            logger.error(f"Batch embedding generation failed: {e}")
            raise EmbeddingServiceError(f"Failed to generate embeddings: {e}") from e
