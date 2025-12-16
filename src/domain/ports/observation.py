"""Observation Repository Interface (Port)"""
from abc import ABC, abstractmethod
from typing import Optional, List

from domain.entities.observation import ObservationEntity
from domain.value_objects.agent_enums import ObservationType


class ObservationRepository(ABC):
    """
    Repository interface for Observation entity

    Defines the contract for Observation persistence operations.
    All methods are async for non-blocking I/O.
    """

    @abstractmethod
    async def create(self, entity: ObservationEntity) -> str:
        """
        Create new observation

        Args:
            entity: ObservationEntity to persist

        Returns:
            Created observation ID (str)
        """
        pass

    @abstractmethod
    async def get_by_id(self, observation_id: str) -> Optional[ObservationEntity]:
        """
        Retrieve observation by ID

        Args:
            observation_id: Observation ID to search for

        Returns:
            ObservationEntity if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_session_id(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[ObservationEntity]:
        """
        Get observations for a session

        Args:
            session_id: Session ID to filter by
            limit: Maximum number of observations to return
            offset: Number of observations to skip

        Returns:
            List of ObservationEntity ordered by created_at
        """
        pass

    @abstractmethod
    async def get_by_loop_id(
        self,
        loop_id: str
    ) -> List[ObservationEntity]:
        """
        Get observations for a specific loop

        Args:
            loop_id: Loop ID to filter by

        Returns:
            List of ObservationEntity ordered by created_at
        """
        pass

    @abstractmethod
    async def get_by_type(
        self,
        session_id: str,
        observation_type: ObservationType,
        limit: int = 100
    ) -> List[ObservationEntity]:
        """
        Get observations by type for a session

        Args:
            session_id: Session ID to filter by
            observation_type: Observation type to filter by
            limit: Maximum number of observations to return

        Returns:
            List of ObservationEntity
        """
        pass

    @abstractmethod
    async def get_errors_by_session_id(
        self,
        session_id: str
    ) -> List[ObservationEntity]:
        """
        Get error observations for a session

        Args:
            session_id: Session ID to filter by

        Returns:
            List of error ObservationEntity
        """
        pass

    @abstractmethod
    async def count_by_session_id(self, session_id: str) -> int:
        """
        Count observations for a session

        Args:
            session_id: Session ID to count for

        Returns:
            Number of observations
        """
        pass
