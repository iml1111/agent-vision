"""SubAgentTrace Repository Interface (Port)"""
from abc import ABC, abstractmethod
from typing import List, Optional

from domain.entities.subagent_trace import SubAgentTraceEntity


class SubAgentTraceRepository(ABC):
    """
    Repository interface for SubAgentTrace entity

    Defines the contract for SubAgentTrace persistence operations.
    Used for debugging and analysis of sub-agent executions.
    All methods are async for non-blocking I/O.
    """

    @abstractmethod
    async def create(self, entity: SubAgentTraceEntity) -> str:
        """
        Create new sub-agent trace document

        Args:
            entity: SubAgentTraceEntity to persist

        Returns:
            Created trace document ID (str)
        """
        pass

    @abstractmethod
    async def get_by_id(self, trace_id: str) -> Optional[SubAgentTraceEntity]:
        """
        Retrieve trace by ID

        Args:
            trace_id: Trace ID to search for

        Returns:
            SubAgentTraceEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_session_id(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[SubAgentTraceEntity]:
        """
        Retrieve all traces for a session

        Args:
            session_id: Parent session ID
            limit: Maximum number of results (default: 100)
            offset: Number of results to skip (default: 0)

        Returns:
            List of SubAgentTraceEntity ordered by created_at
        """
        pass

    @abstractmethod
    async def get_by_parent_message_id(
        self,
        parent_message_id: str
    ) -> Optional[SubAgentTraceEntity]:
        """
        Retrieve trace by parent message ID

        Each Supervisor TOOL_USE message maps to one sub-agent trace.

        Args:
            parent_message_id: Supervisor TOOL_USE message ID

        Returns:
            SubAgentTraceEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def delete(self, trace_id: str) -> bool:
        """
        Delete trace document

        Args:
            trace_id: Trace ID to delete

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    async def delete_by_session_id(self, session_id: str) -> int:
        """
        Delete all traces for a session

        Args:
            session_id: Parent session ID

        Returns:
            Number of deleted documents
        """
        pass

    @abstractmethod
    async def update_parent_message_id(
        self,
        trace_id: str,
        parent_message_id: str
    ) -> bool:
        """
        Update parent_message_id for a trace.

        Used to fix the timing issue where trace is saved before
        the SDK yields the TOOL_USE event with the correct ID.

        Args:
            trace_id: Trace ID to update
            parent_message_id: Correct parent message ID from TOOL_USE event

        Returns:
            True if updated, False if not found
        """
        pass
