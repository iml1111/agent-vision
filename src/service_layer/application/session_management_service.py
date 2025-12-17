"""
Session Management Service

Session lifecycle management for agent sessions.
Handles CRUD operations and session state queries.
"""
from typing import Optional, List

from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from adapters.mongodb.collections.message_adapter import MessageAdapter
from adapters.repositories.mongodb.agent_session import MongoAgentSessionRepository
from adapters.repositories.mongodb.message import MongoMessageRepository
from domain.entities.agent_session import AgentSessionEntity
from domain.entities.message import MessageEntity
from domain.value_objects.agent_enums import SessionStatus
from domain.value_objects.agent_types import SessionStatusVO
from domain.exceptions import AgentSessionNotFoundError


class SessionManagementService:
    """
    Session lifecycle management service.

    Manages session CRUD operations:
    - Create new sessions
    - Query session status and messages
    - Archive and delete sessions
    """

    def __init__(self, db_client: MongoDBClient):
        """
        Initialize the session management service.

        Args:
            db_client: MongoDB client for database access
        """
        self._session_repo = MongoAgentSessionRepository(
            AgentSessionAdapter(db_client.db)
        )
        self._message_repo = MongoMessageRepository(
            MessageAdapter(db_client.db)
        )

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

    async def get_session_status(self, session_id: str) -> SessionStatusVO:
        """
        Get session status with metadata.

        Args:
            session_id: Session ID

        Returns:
            SessionStatusVO with session status and details
        """
        session = await self.get_session(session_id)
        message_count = await self._message_repo.count_by_session_id(session_id)

        return SessionStatusVO(
            session_id=session.id,
            status=session.status.value,
            message_count=message_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
            archived_at=session.archived_at
        )

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

    async def archive_session(self, session_id: str) -> bool:
        """
        Archive a session.

        Args:
            session_id: Session ID to archive

        Returns:
            True if archived successfully
        """
        session = await self.get_session(session_id)

        if session.status == SessionStatus.ARCHIVED:
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
