"""
Agent Orchestration Service

Conversational agent service for continuous dialogue-based growth analysis.
"""
from typing import Dict, Any, Optional, List

from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from adapters.mongodb.collections.message_adapter import MessageAdapter
from adapters.repositories.mongodb.agent_session import MongoAgentSessionRepository
from adapters.repositories.mongodb.message import MongoMessageRepository
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.agent.client import GrowthAgentClient
from domain.entities.agent_session import AgentSessionEntity
from domain.entities.message import MessageEntity
from domain.value_objects.agent_enums import SessionStatus, MessageRole
from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
)
from .growth_memory_service import GrowthMemoryService


class AgentOrchestrationService:
    """
    Conversational orchestration service for growth agent sessions.

    Manages continuous dialogue sessions where users can:
    - Start conversations with goals
    - Send messages and receive agent responses
    - Archive sessions for later reference
    """

    def __init__(
        self,
        db_client: MongoDBClient,
        embedding_client: OpenAIEmbeddingClient
    ):
        """
        Initialize the orchestration service.

        Args:
            db_client: MongoDB client for database access
            embedding_client: OpenAI client for embeddings
        """
        self._db_client = db_client
        self._embedding_client = embedding_client

        # Initialize repositories
        self._session_repo = MongoAgentSessionRepository(
            AgentSessionAdapter(db_client.db)
        )
        self._message_repo = MongoMessageRepository(
            MessageAdapter(db_client.db)
        )

        # Initialize services
        self._memory_service = GrowthMemoryService(db_client, embedding_client)

    async def create_session(self) -> AgentSessionEntity:
        """
        Create a new agent session.

        Goal will be automatically set from the first message sent to the session.

        Returns:
            Created AgentSessionEntity
        """
        session = AgentSessionEntity.create()

        session_id = await self._session_repo.create(session)
        return await self._session_repo.get_by_id(session_id)

    async def get_session(self, session_id: str) -> AgentSessionEntity:
        """
        Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            AgentSessionEntity

        Raises:
            AgentSessionNotFoundError: If session not found
        """
        session = await self._session_repo.get_by_id(session_id)
        if not session:
            raise AgentSessionNotFoundError(f"Session {session_id} not found")
        return session

    async def get_session_status(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get session status.

        Args:
            session_id: Session ID

        Returns:
            Dict with session status and details
        """
        session = await self.get_session(session_id)
        message_count = await self._message_repo.count_by_session_id(session_id)

        return {
            "session_id": session.id,
            "goal": session.goal,
            "status": session.status.value,
            "message_count": message_count,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "archived_at": session.archived_at.isoformat() if session.archived_at else None,
            "archive_reason": session.archive_reason
        }

    async def process_message(
        self,
        session_id: str,
        content: str
    ) -> Dict[str, Any]:
        """
        Process a user message and get agent response.

        Args:
            session_id: Session ID
            content: Message content from user

        Returns:
            Dict with agent response and metadata
        """
        session = await self.get_session(session_id)

        # Validate session state
        if session.status == SessionStatus.ARCHIVED:
            raise InvalidSessionStateError(
                f"Session {session_id} is archived. Unarchive or create a new session."
            )

        # Ensure session is active
        if session.status == SessionStatus.PAUSED:
            await self._session_repo.update_status(session_id, SessionStatus.ACTIVE)

        # Set goal from first message if not set
        if not session.has_goal():
            await self._session_repo.update_goal(session_id, content)
            session = await self.get_session(session_id)

        # Save user message
        user_message = MessageEntity.create(
            session_id=session_id,
            role=MessageRole.USER,
            content=content
        )
        await self._message_repo.create(user_message)

        try:
            # Load conversation context
            recent_messages = await self._message_repo.get_recent_by_session_id(
                session_id=session_id,
                limit=20
            )

            # Build context for agent
            conversation_context = self._build_conversation_context(
                session=session,
                messages=recent_messages
            )

            # Execute agent
            async with GrowthAgentClient(max_turns=50) as client:
                client.set_session_context({
                    "session_id": session_id
                })

                result = await client.run_query(conversation_context)

            # Save assistant response
            assistant_message = MessageEntity.create(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=result.get("text_response", ""),
                metadata={
                    "tool_calls": result.get("tool_calls", []),
                    "model": result.get("model"),
                    "usage": result.get("usage")
                }
            )
            await self._message_repo.create(assistant_message)

            return {
                "session_id": session_id,
                "role": MessageRole.ASSISTANT.value,
                "content": result.get("text_response", ""),
                "tool_calls": result.get("tool_calls", []),
                "created_at": assistant_message.created_at.isoformat()
            }

        except Exception as e:
            # Save error as system message
            error_message = MessageEntity.create(
                session_id=session_id,
                role=MessageRole.SYSTEM,
                content=f"Error processing message: {str(e)}",
                metadata={"error": True, "error_type": type(e).__name__}
            )
            await self._message_repo.create(error_message)
            raise

    def _build_conversation_context(
        self,
        session: AgentSessionEntity,
        messages: List[MessageEntity]
    ) -> str:
        """
        Build conversation context for agent.

        Args:
            session: Current session entity
            messages: Recent messages (chronological order)

        Returns:
            Formatted context string for agent
        """
        context_parts = []

        if session.goal:
            context_parts.append(f"Goal: {session.goal}")
            context_parts.append("")

        if session.context:
            context_parts.append("Session Context:")
            for key, value in session.context.items():
                context_parts.append(f"  {key}: {value}")
            context_parts.append("")

        if messages:
            context_parts.append("Conversation History:")
            for msg in messages:
                role_label = msg.role.value.upper()
                context_parts.append(f"[{role_label}]: {msg.content}")
            context_parts.append("")

        return "\n".join(context_parts)

    async def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[MessageEntity]:
        """
        Get conversation messages for a session.

        Args:
            session_id: Session ID
            limit: Maximum number of messages to return
            offset: Number of messages to skip

        Returns:
            List of MessageEntity ordered by created_at ascending
        """
        await self.get_session(session_id)

        return await self._message_repo.get_by_session_id(
            session_id=session_id,
            limit=limit,
            offset=offset
        )

    async def archive_session(
        self,
        session_id: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Archive a session.

        Args:
            session_id: Session ID to archive
            reason: Optional archive reason

        Returns:
            True if archived successfully
        """
        session = await self.get_session(session_id)

        if session.status == SessionStatus.ARCHIVED:
            raise InvalidSessionStateError(
                f"Session {session_id} is already archived"
            )

        return await self._session_repo.archive_session(session_id, reason)

    async def delete_session(self, session_id: str) -> bool:
        """
        Delete a session and all its messages.

        Args:
            session_id: Session ID to delete

        Returns:
            True if deleted successfully
        """
        await self.get_session(session_id)

        # Delete all messages first
        await self._message_repo.delete_by_session_id(session_id)

        # Delete session
        return await self._session_repo.delete(session_id)
