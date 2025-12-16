"""Agent Session Repository Interface (Port)"""
from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.agent_session import AgentSessionEntity
from domain.value_objects.agent_enums import SessionStatus


class AgentSessionRepository(ABC):
    """
    Repository interface for AgentSession entity

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
        status: SessionStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Update session status

        Args:
            session_id: Session ID to update
            status: New status
            error_message: Optional error message (for FAILED status)

        Returns:
            True if update was successful
        """
        pass

    @abstractmethod
    async def increment_loop_count(self, session_id: str) -> bool:
        """
        Increment the current loop count

        Args:
            session_id: Session ID to update

        Returns:
            True if update was successful
        """
        pass

    @abstractmethod
    async def set_hitl_request(
        self,
        session_id: str,
        hitl_request: dict
    ) -> bool:
        """
        Set HITL request and update status to WAITING_HITL

        Args:
            session_id: Session ID to update
            hitl_request: HITL request data

        Returns:
            True if update was successful
        """
        pass

    @abstractmethod
    async def clear_hitl_request(self, session_id: str) -> bool:
        """
        Clear HITL request after response received

        Args:
            session_id: Session ID to update

        Returns:
            True if update was successful
        """
        pass

    @abstractmethod
    async def set_final_decision(
        self,
        session_id: str,
        final_decision: dict
    ) -> bool:
        """
        Set final decision and mark session as COMPLETED

        Args:
            session_id: Session ID to update
            final_decision: Final decision data

        Returns:
            True if update was successful
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
