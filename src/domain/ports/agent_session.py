"""Agent Session Repository Interface (Port)"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

from domain.entities.agent_session import AgentSessionEntity
from domain.value_objects.agent_enums import SessionStatus


class AgentSessionRepository(ABC):
    """
    Repository interface for AgentSession entity (conversational model)

    Defines the contract for AgentSession persistence operations.
    All methods are async for non-blocking I/O.
    """

    @abstractmethod
    async def create(self, entity: AgentSessionEntity) -> str:
        """
        Create new agent session

        Args:
            entity: AgentSessionEntity to persist

        Returns:
            Created session ID (str)
        """
        pass

    @abstractmethod
    async def get_by_id(self, session_id: str) -> Optional[AgentSessionEntity]:
        """
        Retrieve agent session by ID

        Args:
            session_id: Session ID to search for

        Returns:
            AgentSessionEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def update_status(
        self,
        session_id: str,
        status: SessionStatus
    ) -> bool:
        """
        Update session status

        Args:
            session_id: Session ID to update
            status: New status

        Returns:
            True if update was successful
        """
        pass

    @abstractmethod
    async def archive_session(self, session_id: str) -> bool:
        """
        Archive a session

        Args:
            session_id: Session ID to archive

        Returns:
            True if archive was successful
        """
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: SessionStatus,
        limit: int = 100
    ) -> List[AgentSessionEntity]:
        """
        Get sessions by status

        Args:
            status: Status to filter by
            limit: Maximum number of sessions to return

        Returns:
            List of AgentSessionEntity
        """
        pass

    @abstractmethod
    async def delete(self, session_id: str) -> bool:
        """
        Delete a session

        Args:
            session_id: Session ID to delete

        Returns:
            True if deletion was successful
        """
        pass

    @abstractmethod
    async def update_claude_session_id(
        self,
        session_id: str,
        claude_session_id: str
    ) -> bool:
        """
        Update Claude session ID for resume capability

        Args:
            session_id: System session ID
            claude_session_id: Claude Agent SDK session ID

        Returns:
            True if update was successful
        """
        pass

    @abstractmethod
    async def clear_claude_session_id(self, session_id: str) -> bool:
        """
        Clear Claude session ID when session expires

        Args:
            session_id: System session ID

        Returns:
            True if update was successful
        """
        pass
