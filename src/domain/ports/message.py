"""Message Repository Interface (Port)"""
from abc import ABC, abstractmethod
from typing import List, Optional

from domain.entities.message import MessageEntity


class MessageRepository(ABC):
    """
    Repository interface for Message entity

    Defines the contract for Message persistence operations.
    All methods are async for non-blocking I/O.
    """

    @abstractmethod
    async def create(self, entity: MessageEntity) -> str:
        """
        Create new message

        Args:
            entity: MessageEntity to persist

        Returns:
            Created message ID (str)
        """
        pass

    @abstractmethod
    async def get_by_id(self, message_id: str) -> Optional[MessageEntity]:
        """
        Retrieve message by ID

        Args:
            message_id: Message ID to search for

        Returns:
            MessageEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_session_id(
        self,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[MessageEntity]:
        """
        Get messages for a session

        Args:
            session_id: Session ID to filter by
            limit: Maximum number of messages to return (None for all)
            offset: Number of messages to skip

        Returns:
            List of MessageEntity ordered by created_at ascending
        """
        pass

    @abstractmethod
    async def get_recent_by_session_id(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[MessageEntity]:
        """
        Get most recent messages for a session (for context building)

        Args:
            session_id: Session ID to filter by
            limit: Maximum number of messages to return

        Returns:
            List of MessageEntity ordered by created_at descending
        """
        pass

    @abstractmethod
    async def count_by_session_id(self, session_id: str) -> int:
        """
        Count messages in a session

        Args:
            session_id: Session ID to count messages for

        Returns:
            Number of messages in the session
        """
        pass

    @abstractmethod
    async def delete_by_session_id(self, session_id: str) -> int:
        """
        Delete all messages for a session

        Args:
            session_id: Session ID to delete messages for

        Returns:
            Number of deleted messages
        """
        pass
