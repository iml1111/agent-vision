"""Agent Loop Repository Interface (Port)"""
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from domain.entities.agent_loop import AgentLoopEntity
from domain.value_objects.agent_enums import LoopPhase


class AgentLoopRepository(ABC):
    """
    Repository interface for AgentLoop entity

    Defines the contract for AgentLoop persistence operations.
    All methods are async for non-blocking I/O.
    """

    @abstractmethod
    async def create(self, entity: AgentLoopEntity) -> str:
        """
        Create new agent loop

        Args:
            entity: AgentLoopEntity to persist

        Returns:
            Created loop ID (str)
        """
        pass

    @abstractmethod
    async def get_by_id(self, loop_id: str) -> Optional[AgentLoopEntity]:
        """
        Retrieve agent loop by ID

        Args:
            loop_id: Loop ID to search for

        Returns:
            AgentLoopEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_session_id(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[AgentLoopEntity]:
        """
        Get all loops for a session

        Args:
            session_id: Session ID to filter by
            limit: Maximum number of loops to return

        Returns:
            List of AgentLoopEntity ordered by iteration
        """
        pass

    @abstractmethod
    async def get_latest_by_session_id(
        self,
        session_id: str
    ) -> Optional[AgentLoopEntity]:
        """
        Get the latest loop for a session

        Args:
            session_id: Session ID to filter by

        Returns:
            Latest AgentLoopEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def update_phase(
        self,
        loop_id: str,
        phase: LoopPhase
    ) -> bool:
        """
        Update loop phase

        Args:
            loop_id: Loop ID to update
            phase: New phase

        Returns:
            True if update was successful
        """
        pass

    @abstractmethod
    async def set_phase_output(
        self,
        loop_id: str,
        phase: LoopPhase,
        output: Dict[str, Any]
    ) -> bool:
        """
        Set output for a specific phase

        Args:
            loop_id: Loop ID to update
            phase: Phase to set output for
            output: Output data

        Returns:
            True if update was successful
        """
        pass
