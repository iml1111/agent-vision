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

    async def distill_session_to_memory(
        self,
        session_id: str,
        session_summary: str,
        key_insights: Optional[List[str]] = None,
        experiment_results: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        Distill a completed session into long-term memories.

        Creates multiple memory entries from session data:
        - Session summary
        - Key insights (if provided)
        - Experiment results (if provided)

        Args:
            session_id: Source session ID
            session_summary: Summary of the session
            key_insights: Optional list of key insights extracted
            experiment_results: Optional list of experiment outcomes

        Returns:
            List of created memory IDs
        """
        created_ids = []

        # Create session summary memory
        summary_id = await self.create_memory(
            content=session_summary,
            memory_type=GrowthMemoryType.SESSION_SUMMARY,
            source_session_id=session_id,
            tags=["session_summary"]
        )
        created_ids.append(summary_id)

        # Create insight memories
        if key_insights:
            for insight in key_insights:
                insight_id = await self.create_memory(
                    content=insight,
                    memory_type=GrowthMemoryType.INSIGHT,
                    source_session_id=session_id,
                    tags=["insight"]
                )
                created_ids.append(insight_id)

        # Create experiment result memories
        if experiment_results:
            for result in experiment_results:
                result_content = self._format_experiment_result(result)
                result_id = await self.create_memory(
                    content=result_content,
                    memory_type=GrowthMemoryType.EXPERIMENT_RESULT,
                    source_session_id=session_id,
                    tags=["experiment_result"],
                    metadata=result
                )
                created_ids.append(result_id)

        return created_ids

    def _format_experiment_result(self, result: Dict[str, Any]) -> str:
        """Format experiment result dict as readable content"""
        parts = []

        if "name" in result:
            parts.append(f"Experiment: {result['name']}")
        if "hypothesis" in result:
            parts.append(f"Hypothesis: {result['hypothesis']}")
        if "outcome" in result:
            parts.append(f"Outcome: {result['outcome']}")
        if "metrics" in result:
            metrics_str = ", ".join(f"{k}: {v}" for k, v in result["metrics"].items())
            parts.append(f"Metrics: {metrics_str}")
        if "learnings" in result:
            parts.append(f"Learnings: {result['learnings']}")

        return "\n".join(parts) if parts else str(result)

    async def delete_memory(self, memory_id: str) -> bool:
        """
        Delete a growth memory.

        Args:
            memory_id: Memory ID to delete

        Returns:
            True if deletion was successful
        """
        return await self._memory_repo.delete(memory_id)
