"""
Observation Service

Manages ephemeral observations (short-term memory) within agent sessions.
"""
from typing import List, Optional, Dict, Any
from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.observation_adapter import ObservationAdapter
from adapters.repositories.mongodb.observation import MongoObservationRepository
from domain.entities.observation import ObservationEntity
from domain.value_objects.agent_enums import ObservationType


class ObservationService:
    """
    Service for managing session observations.

    Observations are ephemeral records of tool executions, context updates,
    errors, and HITL responses within a session.
    """

    def __init__(self, db_client: MongoDBClient):
        """
        Initialize the observation service.

        Args:
            db_client: MongoDB client for database access
        """
        self._db_client = db_client
        self._observation_repo = MongoObservationRepository(
            ObservationAdapter(db_client.db)
        )

    async def record_tool_result(
        self,
        session_id: str,
        loop_id: Optional[str],
        tool_name: str,
        result: Dict[str, Any],
        is_error: bool = False
    ) -> str:
        """
        Record a tool execution result.

        Args:
            session_id: Parent session ID
            loop_id: Optional parent loop ID
            tool_name: Name of the tool that was executed
            result: Tool execution result
            is_error: Whether the result indicates an error

        Returns:
            Created observation ID
        """
        observation = ObservationEntity.create(
            session_id=session_id,
            observation_type=ObservationType.TOOL_RESULT,
            content={"tool_result": result},
            loop_id=loop_id,
            tool_name=tool_name,
            is_error=is_error
        )
        return await self._observation_repo.create(observation)

    async def record_context(
        self,
        session_id: str,
        loop_id: Optional[str],
        context: Dict[str, Any]
    ) -> str:
        """
        Record context information.

        Args:
            session_id: Parent session ID
            loop_id: Optional parent loop ID
            context: Context data to record

        Returns:
            Created observation ID
        """
        observation = ObservationEntity.create(
            session_id=session_id,
            observation_type=ObservationType.CONTEXT,
            content=context,
            loop_id=loop_id
        )
        return await self._observation_repo.create(observation)

    async def record_error(
        self,
        session_id: str,
        loop_id: Optional[str],
        error_message: str,
        error_details: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Record an error observation.

        Args:
            session_id: Parent session ID
            loop_id: Optional parent loop ID
            error_message: Error message
            error_details: Optional additional error details

        Returns:
            Created observation ID
        """
        observation = ObservationEntity.create(
            session_id=session_id,
            observation_type=ObservationType.ERROR,
            content={
                "error_message": error_message,
                "error_details": error_details or {}
            },
            loop_id=loop_id,
            is_error=True
        )
        return await self._observation_repo.create(observation)

    async def record_hitl_response(
        self,
        session_id: str,
        loop_id: Optional[str],
        response: Dict[str, Any]
    ) -> str:
        """
        Record a HITL response.

        Args:
            session_id: Parent session ID
            loop_id: Optional parent loop ID
            response: HITL response data

        Returns:
            Created observation ID
        """
        observation = ObservationEntity.create(
            session_id=session_id,
            observation_type=ObservationType.HITL_RESPONSE,
            content=response,
            loop_id=loop_id
        )
        return await self._observation_repo.create(observation)

    async def record_rag_retrieval(
        self,
        session_id: str,
        loop_id: Optional[str],
        query: str,
        results: List[Dict[str, Any]]
    ) -> str:
        """
        Record a RAG retrieval result.

        Args:
            session_id: Parent session ID
            loop_id: Optional parent loop ID
            query: The search query used
            results: Retrieved memory results

        Returns:
            Created observation ID
        """
        observation = ObservationEntity.create(
            session_id=session_id,
            observation_type=ObservationType.RAG_RETRIEVAL,
            content={
                "query": query,
                "results": results,
                "result_count": len(results)
            },
            loop_id=loop_id
        )
        return await self._observation_repo.create(observation)

    async def get_observations(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[ObservationEntity]:
        """
        Get observations for a session.

        Args:
            session_id: Session ID to get observations for
            limit: Maximum number of observations to return
            offset: Number of observations to skip

        Returns:
            List of observations ordered by creation time (newest first)
        """
        return await self._observation_repo.get_by_session_id(
            session_id=session_id,
            limit=limit,
            offset=offset
        )

    async def get_loop_observations(
        self,
        loop_id: str
    ) -> List[ObservationEntity]:
        """
        Get observations for a specific loop.

        Args:
            loop_id: Loop ID to get observations for

        Returns:
            List of observations for the loop
        """
        return await self._observation_repo.get_by_loop_id(loop_id)

    async def get_errors(
        self,
        session_id: str
    ) -> List[ObservationEntity]:
        """
        Get error observations for a session.

        Args:
            session_id: Session ID to get errors for

        Returns:
            List of error observations
        """
        return await self._observation_repo.get_errors_by_session_id(session_id)

    async def get_session_summary(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get a summary of session observations.

        Args:
            session_id: Session ID to summarize

        Returns:
            Summary dict with counts and key metrics
        """
        total_count = await self._observation_repo.count_by_session_id(session_id)
        errors = await self.get_errors(session_id)

        # Get observations by type
        tool_results = await self._observation_repo.get_by_type(
            session_id, ObservationType.TOOL_RESULT, limit=1000
        )
        rag_retrievals = await self._observation_repo.get_by_type(
            session_id, ObservationType.RAG_RETRIEVAL, limit=1000
        )

        # Extract unique tools used
        tools_used = set()
        for obs in tool_results:
            if obs.tool_name:
                tools_used.add(obs.tool_name)

        return {
            "total_observations": total_count,
            "error_count": len(errors),
            "tool_call_count": len(tool_results),
            "rag_retrieval_count": len(rag_retrievals),
            "tools_used": list(tools_used)
        }
