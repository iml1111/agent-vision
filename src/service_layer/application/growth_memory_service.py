"""
GrowthMemory Service

Service for creating and managing Growth Memory documents.
Handles session summarization, embedding generation, and memory persistence.
"""
from logging_config import get_logger

from adapters.anthropic.summarization_client import ClaudeSummarizationClient
from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from adapters.mongodb.collections.growth_memory_adapter import GrowthMemoryAdapter
from adapters.mongodb.collections.message_adapter import MessageAdapter
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.repositories.mongodb.agent_session import MongoAgentSessionRepository
from adapters.repositories.mongodb.growth_memory import MongoGrowthMemoryRepository
from adapters.repositories.mongodb.message import MongoMessageRepository
from domain.entities.growth_memory import GrowthMemoryEntity
from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
    SummarizationError,
)
from domain.value_objects.agent_enums import SessionStatus

logger = get_logger(__name__)


class GrowthMemoryService:
    """
    Service for creating and managing Growth Memory documents.

    Handles:
    - Session summarization via Claude API
    - Embedding generation for vector search
    - Memory document persistence
    - Duplicate memory prevention
    """

    def __init__(
        self,
        db_client: MongoDBClient,
        summarization_client: ClaudeSummarizationClient,
        embedding_client: OpenAIEmbeddingClient
    ):
        """
        Initialize the GrowthMemory service.

        Args:
            db_client: MongoDB client for database access
            summarization_client: Claude API client for summarization
            embedding_client: OpenAI client for embedding generation
        """
        self._session_repo = MongoAgentSessionRepository(
            AgentSessionAdapter(db_client.db)
        )
        self._message_repo = MongoMessageRepository(
            MessageAdapter(db_client.db)
        )
        self._memory_repo = MongoGrowthMemoryRepository(
            GrowthMemoryAdapter(db_client.db)
        )
        self._summarization_client = summarization_client
        self._embedding_client = embedding_client

    async def create_memory_from_session(self, session_id: str) -> str:
        """
        Create GrowthMemory from archived session.

        Pipeline:
        1. Validate session is archived
        2. Check if memory already exists (prevent duplicates)
        3. Get all session messages
        4. Summarize with Claude API
        5. Generate embedding for vector search
        6. Save GrowthMemory document

        Args:
            session_id: Session ID to create memory from

        Returns:
            Created memory document ID

        Raises:
            AgentSessionNotFoundError: If session not found
            InvalidSessionStateError: If session is not archived
            SummarizationError: If summarization fails
        """
        # 1. Validate session exists and is archived
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            raise AgentSessionNotFoundError(f"Session {session_id} not found")

        if session.status != SessionStatus.ARCHIVED:
            raise InvalidSessionStateError(
                f"Session {session_id} is not archived (status: {session.status.value}). "
                "Memory can only be created from archived sessions."
            )

        # 2. Check if memory already exists
        existing = await self._memory_repo.get_by_session_id(session_id)
        if existing:
            logger.info(f"Memory already exists for session {session_id}: {existing.id}")
            return existing.id

        # 3. Get all messages
        messages = await self._message_repo.get_by_session_id(session_id)
        if not messages:
            raise SummarizationError(f"No messages found for session {session_id}")

        logger.info(f"Summarizing session {session_id} with {len(messages)} messages")

        # 4. Summarize with Claude API
        summary = await self._summarization_client.summarize_session(messages)

        # 5. Generate embedding for vector search
        embedding_text = summary.get_embedding_text()
        if not embedding_text:
            raise SummarizationError(
                f"Failed to generate embedding text for session {session_id}"
            )

        content_vector = await self._embedding_client.generate_embedding(embedding_text)
        if not content_vector:
            raise SummarizationError(
                f"Failed to generate embedding vector for session {session_id}"
            )
        logger.debug(f"Generated embedding for session {session_id}")

        # 6. Create and save entity
        memory = GrowthMemoryEntity.create(
            session_id=session_id,
            problem_snapshot=summary.problem_snapshot,
            bottleneck_evidence=summary.bottleneck_evidence,
            hypotheses=summary.hypotheses,
            experiment_cards=summary.experiment_cards,
            outcome=summary.outcome,
            learnings_next_actions=summary.learnings_next_actions,
            content_vector=content_vector,
            vector_text=embedding_text,
            message_count=len(messages),
            session_created_at=session.created_at,
            session_archived_at=session.archived_at
        )

        memory_id = await self._memory_repo.create(memory)
        logger.info(f"Created GrowthMemory {memory_id} for session {session_id}")

        return memory_id
