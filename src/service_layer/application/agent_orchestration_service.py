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
from domain.value_objects.agent_types import MessageEnqueueResultVO
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
        Execute agent and save response.

        Worker calls this method after consuming from SQS.

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

            # Get saved SDK session ID for resume
            resume_session_id = session.sdk_session_id

            # Execute agent with SDK session resume support
            # SDK maintains conversation history automatically when resuming
            async with GrowthAgentClient(
                max_turns=100,
                resume_session_id=resume_session_id
            ) as client:
                result = await client.run_query(user_message.content)

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
