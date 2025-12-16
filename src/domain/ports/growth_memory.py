"""Growth Memory Repository Interface (Port)"""
from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.growth_memory import GrowthMemoryEntity
from domain.value_objects.agent_enums import GrowthMemoryType


class GrowthMemoryRepository(ABC):
    """
    Repository interface for GrowthMemory entity

    Defines the contract for GrowthMemory persistence operations.
    Includes vector search capabilities for RAG retrieval.
    All methods are async for non-blocking I/O.
    """

    @abstractmethod
    async def create(self, entity: GrowthMemoryEntity) -> str:
        """
        Create new growth memory

        Args:
            entity: GrowthMemoryEntity to persist

        Returns:
            Created memory ID (str)
        """
        pass

    @abstractmethod
    async def get_by_id(self, memory_id: str) -> Optional[GrowthMemoryEntity]:
        """
        Retrieve growth memory by ID

        Args:
            memory_id: Memory ID to search for

        Returns:
            GrowthMemoryEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def vector_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        memory_type: Optional[GrowthMemoryType] = None,
        min_score: float = 0.7
    ) -> List[GrowthMemoryEntity]:
        """
        Vector similarity search for relevant memories

        Args:
            query_embedding: Query embedding vector (1536 dimensions)
            limit: Maximum number of results to return
            memory_type: Optional filter by memory type
            min_score: Minimum similarity score (0-1)

        Returns:
            List of GrowthMemoryEntity ordered by similarity score
        """
        pass

    @abstractmethod
    async def get_recent(
        self,
        limit: int = 10,
        memory_type: Optional[GrowthMemoryType] = None
    ) -> List[GrowthMemoryEntity]:
        """
        Get most recent memories

        Args:
            limit: Maximum number of memories to return
            memory_type: Optional filter by memory type

        Returns:
            List of GrowthMemoryEntity ordered by created_at descending
        """
        pass

    @abstractmethod
    async def get_by_session_id(
        self,
        session_id: str
    ) -> List[GrowthMemoryEntity]:
        """
        Get memories associated with a session

        Args:
            session_id: Source session ID to filter by

        Returns:
            List of GrowthMemoryEntity
        """
        pass

    @abstractmethod
    async def get_by_tags(
        self,
        tags: List[str],
        limit: int = 10
    ) -> List[GrowthMemoryEntity]:
        """
        Get memories by tags

        Args:
            tags: Tags to filter by (OR logic)
            limit: Maximum number of memories to return

        Returns:
            List of GrowthMemoryEntity
        """
        pass

    @abstractmethod
    async def delete(self, memory_id: str) -> bool:
        """
        Delete a growth memory

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deletion was successful
        """
        pass
