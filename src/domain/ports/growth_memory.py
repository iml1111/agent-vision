"""GrowthMemory Repository Interface (Port)"""
from abc import ABC, abstractmethod
from typing import List, Optional

from domain.entities.growth_memory import GrowthMemoryEntity


class GrowthMemoryRepository(ABC):
    """
    Repository interface for GrowthMemory entity

    Defines the contract for GrowthMemory persistence operations.
    All methods are async for non-blocking I/O.
    """

    @abstractmethod
    async def create(self, entity: GrowthMemoryEntity) -> str:
        """
        Create new growth memory document

        Args:
            entity: GrowthMemoryEntity to persist

        Returns:
            Created memory document ID (str)
        """
        pass

    @abstractmethod
    async def get_by_id(self, memory_id: str) -> Optional[GrowthMemoryEntity]:
        """
        Retrieve memory by ID

        Args:
            memory_id: Memory ID to search for

        Returns:
            GrowthMemoryEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_session_id(self, session_id: str) -> Optional[GrowthMemoryEntity]:
        """
        Retrieve memory by original session ID

        Args:
            session_id: Original session ID

        Returns:
            GrowthMemoryEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def vector_search(
        self,
        query_vector: List[float],
        limit: int = 5,
        min_score: float = 0.7
    ) -> List[GrowthMemoryEntity]:
        """
        Search memories by vector similarity

        Uses Atlas Vector Search on content_vector field.

        Args:
            query_vector: Query embedding vector (1536 dimensions)
            limit: Maximum number of results
            min_score: Minimum similarity score threshold

        Returns:
            List of GrowthMemoryEntity ordered by similarity
        """
        pass

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """
        Delete memory document

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def delete_by_session_id(self, session_id: str) -> bool:
        """
        Delete memory by original session ID

        Args:
            session_id: Original session ID

        Returns:
            True if deleted, False if not found
        """
        pass
