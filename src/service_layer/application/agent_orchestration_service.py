"""
Agent Orchestration Service

Conversational agent service for continuous dialogue-based growth analysis.
Supports async processing via SQS worker.
"""
from typing import Dict, Any, Optional, List

from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from adapters.mongodb.collections.message_adapter import MessageAdapter
from adapters.repositories.mongodb.agent_session import MongoAgentSessionRepository
from adapters.repositories.mongodb.message import MongoMessageRepository
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.aws.sqs_producer import SQSProducerAdapter
from adapters.agent.client import GrowthAgentClient
from domain.entities.agent_session import AgentSessionEntity
from domain.entities.message import MessageEntity
from domain.value_objects.agent_enums import SessionStatus, MessageRole
from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
    SDKSessionExpiredError,
)
from loguru import logger
from .growth_memory_service import GrowthMemoryService


class AgentOrchestrationService:
    """
    Conversational orchestration service for growth agent sessions.

    Manages continuous dialogue sessions where users can:
    - Send messages and receive agent responses (async via worker)
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
            "status": session.status.value,
            "message_count": message_count,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "archived_at": session.archived_at.isoformat() if session.archived_at else None
        }

    async def enqueue_message(
        self,
        session_id: str,
        content: str,
        sqs_producer: SQSProducerAdapter
    ) -> Dict[str, Any]:
        """
        Save user message and enqueue for async processing.

        API endpoint calls this method for fast response.
        Actual agent execution happens in worker via execute_agent_response().

        Args:
            session_id: Session ID
            content: Message content from user
            sqs_producer: SQS producer for enqueueing

        Returns:
            Dict with session_id, status, and user_message_id
        """
        session = await self.get_session(session_id)

        # Validate session state
        if session.status == SessionStatus.ARCHIVED:
            raise InvalidSessionStateError(
                f"Session {session_id} is archived. Create a new session."
            )

        if session.status == SessionStatus.PROCESSING:
            raise InvalidSessionStateError(
                f"Session {session_id} is processing. Please wait for the response."
            )

        # Save user message
        user_message = MessageEntity.create(
            session_id=session_id,
            role=MessageRole.USER,
            content=content
        )
        message_id = await self._message_repo.create(user_message)

        # Set session to PROCESSING state
        await self._session_repo.update_status(session_id, SessionStatus.PROCESSING)

        # Enqueue to SQS for async processing
        sqs_producer.enqueue_task(
            task_type="process_agent_response",
            data={
                "session_id": session_id,
                "user_message_id": message_id
            },
            message_group_id=session_id  # Per-session ordering
        )

        logger.info(f"Message enqueued for session {session_id}, message_id={message_id}")

        return {
            "session_id": session_id,
            "status": "processing",
            "user_message_id": message_id
        }

    async def execute_agent_response(
        self,
        session_id: str,
        user_message_id: str
    ) -> None:
        """
        Execute agent and save response.

        Worker calls this method after consuming from SQS.
        This is the heavy-lifting part that was previously in process_message().

        Args:
            session_id: Session ID
            user_message_id: ID of the user message to respond to
        """
        session = await self.get_session(session_id)

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

            # Get saved SDK session ID for resume
            resume_session_id = session.sdk_session_id

            # Execute agent with SDK session resume support
            async with GrowthAgentClient(
                max_turns=100,
                resume_session_id=resume_session_id
            ) as client:
                client.set_session_context({
                    "session_id": session_id
                })

                result = await client.run_query(conversation_context)

                # Save new SDK session ID if changed
                new_sdk_session_id = client.sdk_session_id
                if new_sdk_session_id and new_sdk_session_id != resume_session_id:
                    await self._session_repo.update_sdk_session_id(
                        session_id, new_sdk_session_id
                    )
                    logger.info(
                        f"Updated SDK session ID for session {session_id}: "
                        f"{resume_session_id} -> {new_sdk_session_id}"
                    )

            # Save assistant response
            assistant_message = MessageEntity.create(
                session_id=session_id,
                role=MessageRole.ASSISTANT,
                content=result.text_response,
                metadata={
                    "tool_calls": [
                        {"id": tc.id, "name": tc.name, "input": tc.input}
                        for tc in result.tool_calls
                    ],
                    "sdk_session_id": new_sdk_session_id,
                    "message_count": result.message_count,
                    "user_message_id": user_message_id
                }
            )
            await self._message_repo.create(assistant_message)

            # Restore session to ACTIVE state
            await self._session_repo.update_status(session_id, SessionStatus.ACTIVE)

            logger.info(f"Agent response completed for session {session_id}")

        except SDKSessionExpiredError:
            # SDK session expired - archive the system session
            logger.warning(f"SDK session expired for session {session_id}, archiving...")
            await self._session_repo.clear_sdk_session_id(session_id)
            await self._archive_session(session_id)

            # Save error message for user to see
            error_message = MessageEntity.create(
                session_id=session_id,
                role=MessageRole.SYSTEM,
                content="Session has expired. Please create a new session.",
                metadata={"error": True, "error_type": "SDKSessionExpiredError"}
            )
            await self._message_repo.create(error_message)

        except Exception as e:
            # Restore session to ACTIVE state on error (allows retry)
            await self._session_repo.update_status(session_id, SessionStatus.ACTIVE)

            # Save error as system message
            error_message = MessageEntity.create(
                session_id=session_id,
                role=MessageRole.SYSTEM,
                content=f"Error processing message: {str(e)}",
                metadata={"error": True, "error_type": type(e).__name__}
            )
            await self._message_repo.create(error_message)

            logger.error(f"Agent execution failed for session {session_id}: {e}")
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

    async def _archive_session(self, session_id: str) -> bool:
        """
        Archive a session (called when SDK session expires).

        Users cannot manually archive sessions - archiving only happens
        when the Claude Agent SDK session expires.

        Args:
            session_id: Session ID to archive

        Returns:
            True if archived successfully
        """
        session = await self.get_session(session_id)

        if session.status == SessionStatus.ARCHIVED:
            # Already archived, skip
            return True

        return await self._session_repo.archive_session(session_id)

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
