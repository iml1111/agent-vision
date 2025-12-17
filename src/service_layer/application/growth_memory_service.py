"""
Growth Memory Service

Manages long-term memory with vector embeddings for RAG retrieval.
"""
from typing import List, Optional, Dict, Any
from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.growth_memory_adapter import GrowthMemoryAdapter
from adapters.repositories.mongodb.growth_memory import MongoGrowthMemoryRepository
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from domain.entities.growth_memory import GrowthMemoryEntity
from domain.value_objects.agent_enums import GrowthMemoryType
from domain.exceptions import EmbeddingServiceError


class GrowthMemoryService:
    """
    Service for managing growth memory (long-term memory).

    Provides vector search capabilities for RAG retrieval and
    memory creation with automatic embedding generation.
    """

    def __init__(
        self,
        db_client: MongoDBClient,
        embedding_client: OpenAIEmbeddingClient
    ):
        """
        Initialize the growth memory service.

        Args:
            db_client: MongoDB client for database access
            embedding_client: OpenAI client for embedding generation
        """
        self._db_client = db_client
        self._embedding_client = embedding_client
        self._memory_repo = MongoGrowthMemoryRepository(
            GrowthMemoryAdapter(db_client.db)
        )

    async def create_memory(
        self,
        content: str,
        memory_type: GrowthMemoryType,
        source_session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a new growth memory with auto-generated embedding.

        Args:
            content: Memory content/text
            memory_type: Type of memory
            source_session_id: Optional source session ID
            tags: Optional tags for filtering
            metadata: Optional additional metadata

        Returns:
            Created memory ID

        Raises:
            EmbeddingServiceError: If embedding generation fails
        """
        # Generate embedding for the content
        embedding = await self._embedding_client.generate_embedding(content)

        # Create memory entity
        memory = GrowthMemoryEntity.create(
            content=content,
            memory_type=memory_type,
            embedding=embedding,
            source_session_id=source_session_id,
            tags=tags,
            metadata=metadata
        )

        return await self._memory_repo.create(memory)

    async def search_relevant_memories(
        self,
        query: str,
        limit: int = 10,
        memory_type: Optional[GrowthMemoryType] = None,
        min_score: float = 0.7
    ) -> List[GrowthMemoryEntity]:
        """
        Search for relevant memories using vector similarity.

        Args:
            query: Natural language search query
            limit: Maximum number of results
            memory_type: Optional filter by memory type
            min_score: Minimum similarity score (0-1)

        Returns:
            List of relevant memories ordered by similarity

        Raises:
            EmbeddingServiceError: If embedding generation fails
        """
        # Generate embedding for the query
        query_embedding = await self._embedding_client.generate_embedding(query)

        # Perform vector search
        return await self._memory_repo.vector_search(
            query_embedding=query_embedding,
            limit=limit,
            memory_type=memory_type,
            min_score=min_score
        )

    async def get_recent_memories(
        self,
        limit: int = 10,
        memory_type: Optional[GrowthMemoryType] = None
    ) -> List[GrowthMemoryEntity]:
        """
        Get most recent memories.

        Args:
            limit: Maximum number of memories to return
            memory_type: Optional filter by memory type

        Returns:
            List of recent memories
        """
        return await self._memory_repo.get_recent(
            limit=limit,
            memory_type=memory_type
        )

    async def get_session_memories(
        self,
        session_id: str
    ) -> List[GrowthMemoryEntity]:
        """
        Get memories associated with a session.

        Args:
            session_id: Session ID to get memories for

        Returns:
            List of memories from the session
        """
        return await self._memory_repo.get_by_session_id(session_id)
