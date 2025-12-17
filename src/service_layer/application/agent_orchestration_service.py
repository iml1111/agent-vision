"""
Agent Orchestration Service

Message processing and agent execution service.
Handles async message enqueueing and agent response generation.
"""
from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from adapters.mongodb.collections.message_adapter import MessageAdapter
from adapters.repositories.mongodb.agent_session import MongoAgentSessionRepository
from adapters.repositories.mongodb.message import MongoMessageRepository
from adapters.aws.sqs_producer import SQSProducerAdapter
from adapters.agent.client import GrowthAgentClient
from domain.entities.message import MessageEntity
from domain.value_objects.agent_enums import SessionStatus, MessageRole
from domain.value_objects.agent_types import MessageEnqueueResultVO, AgentMessageType
from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
    SDKSessionExpiredError,
)
from loguru import logger


class AgentOrchestrationService:
    """
    Agent message processing and execution service.

    Handles:
    - Message enqueueing for async processing
    - Agent response execution (via worker)
    """

    def __init__(self, db_client: MongoDBClient):
        """
        Initialize the orchestration service.

        Args:
            db_client: MongoDB client for database access
        """
        self._session_repo = MongoAgentSessionRepository(
            AgentSessionAdapter(db_client.db)
        )
        self._message_repo = MongoMessageRepository(
            MessageAdapter(db_client.db)
        )

    async def _get_session(self, session_id: str):
        """
        Internal session fetch.

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

    async def enqueue_message(
        self,
        session_id: str,
        content: str,
        sqs_producer: SQSProducerAdapter
    ) -> MessageEnqueueResultVO:
        """
        Save user message and enqueue for async processing.

        API endpoint calls this method for fast response.
        Actual agent execution happens in worker via execute_agent_response().

        Args:
            session_id: Session ID
            content: Message content from user
            sqs_producer: SQS producer for enqueueing

        Returns:
            MessageEnqueueResultVO with session_id, status, and user_message_id
        """
        session = await self._get_session(session_id)

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

        return MessageEnqueueResultVO(
            session_id=session_id,
            status="processing",
            user_message_id=message_id
        )

    async def execute_agent_response(
        self,
        session_id: str,
        user_message_id: str
    ) -> None:
        """
        Execute agent and save each event to DB in real-time.

        Worker calls this method after consuming from SQS.
        Each streaming event (TEXT, TOOL_USE, etc.) is saved as a separate message.

        Args:
            session_id: Session ID
            user_message_id: ID of the user message to respond to
        """
        session = await self._get_session(session_id)

        try:
            # Get user message content
            user_message = await self._message_repo.get_by_id(user_message_id)
            if not user_message:
                raise ValueError(f"User message {user_message_id} not found")

            # Get saved Claude session ID for resume
            resume_session_id = session.claude_session_id
            sequence = 0

            # Execute agent with streaming - save each event to DB
            async with GrowthAgentClient(resume_session_id=resume_session_id) as client:
                async for event in client.stream_query(user_message.content):
                    sequence += 1

                    if event.type == AgentMessageType.TEXT:
                        # Save text response
                        message = MessageEntity.create(
                            session_id=session_id,
                            role=MessageRole.ASSISTANT,
                            content=event.content or "",
                            metadata={
                                "event_type": "text",
                                "sequence": sequence,
                                "user_message_id": user_message_id
                            }
                        )
                        await self._message_repo.create(message)
                        logger.debug(f"Saved TEXT event #{sequence} for session {session_id}")

                    elif event.type == AgentMessageType.TOOL_USE and event.tool_call:
                        # Save tool use event
                        message = MessageEntity.create(
                            session_id=session_id,
                            role=MessageRole.ASSISTANT,
                            content=f"Tool: {event.tool_call.name}",
                            metadata={
                                "event_type": "tool_use",
                                "sequence": sequence,
                                "tool_call": {
                                    "id": event.tool_call.id,
                                    "name": event.tool_call.name,
                                    "input": event.tool_call.input
                                },
                                "user_message_id": user_message_id
                            }
                        )
                        await self._message_repo.create(message)
                        logger.debug(f"Saved TOOL_USE event #{sequence} for session {session_id}")

                    elif event.type == AgentMessageType.COMPLETE:
                        # Update Claude session ID if available
                        new_claude_session_id = event.claude_session_id
                        if new_claude_session_id and new_claude_session_id != resume_session_id:
                            await self._session_repo.update_claude_session_id(
                                session_id, new_claude_session_id
                            )
                            logger.info(
                                f"Updated Claude session ID for session {session_id}: "
                                f"{resume_session_id} -> {new_claude_session_id}"
                            )

            # Restore session to ACTIVE state
            await self._session_repo.update_status(session_id, SessionStatus.ACTIVE)

            logger.info(f"Agent response completed for session {session_id}, {sequence} events saved")

        except SDKSessionExpiredError:
            # Claude session expired - archive the system session
            logger.warning(f"Claude session expired for session {session_id}, archiving...")
            await self._session_repo.clear_claude_session_id(session_id)
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

    async def _archive_session(self, session_id: str) -> bool:
        """
        Internal archive for SDK session expiration.

        Args:
            session_id: Session ID to archive

        Returns:
            True if archived successfully
        """
        session = await self._get_session(session_id)

        if session.status == SessionStatus.ARCHIVED:
            return True

        return await self._session_repo.archive_session(session_id)
