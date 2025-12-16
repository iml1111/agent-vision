"""
Agent Orchestration Service

Main service for managing agent sessions and the Plan→Act→Observe→Critique→Decide loop.
"""
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from adapters.mongodb.collections.agent_loop_adapter import AgentLoopAdapter
from adapters.repositories.mongodb.agent_session import MongoAgentSessionRepository
from adapters.repositories.mongodb.agent_loop import MongoAgentLoopRepository
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.agent.client import GrowthAgentClient
from domain.entities.agent_session import AgentSessionEntity
from domain.entities.agent_loop import AgentLoopEntity
from domain.value_objects.agent_enums import SessionStatus, LoopPhase, DecisionType
from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
    LoopLimitExceededError,
)
from .observation_service import ObservationService
from .growth_memory_service import GrowthMemoryService


class AgentOrchestrationService:
    """
    Main orchestration service for growth agent sessions.

    Manages the complete lifecycle of agent sessions including:
    - Session creation and status management
    - Agent loop execution (Plan→Act→Observe→Critique→Decide)
    - HITL (Human-in-the-Loop) handling
    - Final decision storage
    """

    def __init__(
        self,
        db_client: MongoDBClient,
        embedding_client: OpenAIEmbeddingClient,
        max_loop_count: int = 10
    ):
        """
        Initialize the orchestration service.

        Args:
            db_client: MongoDB client for database access
            embedding_client: OpenAI client for embeddings
            max_loop_count: Maximum loops per session
        """
        self._db_client = db_client
        self._embedding_client = embedding_client
        self._max_loop_count = max_loop_count

        # Initialize repositories
        self._session_repo = MongoAgentSessionRepository(
            AgentSessionAdapter(db_client.db)
        )
        self._loop_repo = MongoAgentLoopRepository(
            AgentLoopAdapter(db_client.db)
        )

        # Initialize services
        self._observation_service = ObservationService(db_client)
        self._memory_service = GrowthMemoryService(db_client, embedding_client)

    async def create_session(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> AgentSessionEntity:
        """
        Create a new agent session.

        Args:
            goal: The goal/objective for the agent
            context: Optional additional context

        Returns:
            Created AgentSessionEntity
        """
        # Create session entity
        session = AgentSessionEntity.create(
            goal=goal,
            context=context or {},
            max_loop_count=self._max_loop_count
        )

        # Persist and return with ID
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

    async def get_session_status(
        self,
        session_id: str
    ) -> Dict[str, Any]:
        """
        Get detailed session status.

        Args:
            session_id: Session ID

        Returns:
            Dict with session status and details
        """
        session = await self.get_session(session_id)
        observation_summary = await self._observation_service.get_session_summary(session_id)

        return {
            "session_id": session.id,
            "status": session.status.value,
            "current_loop_count": session.current_loop_count,
            "max_loop_count": session.max_loop_count,
            "hitl_request": session.hitl_request,
            "final_decision": session.final_decision,
            "error_message": session.error_message,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "observation_summary": observation_summary
        }

    async def process_message(
        self,
        session_id: str,
        content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a message for a session (starts or continues agent loop).

        Args:
            session_id: Session ID
            content: Optional message content (for initial query)

        Returns:
            Dict with processing result
        """
        session = await self.get_session(session_id)

        # Validate session state
        if session.is_terminal():
            raise InvalidSessionStateError(
                f"Session {session_id} is in terminal state: {session.status.value}"
            )

        if session.status == SessionStatus.WAITING_HITL:
            raise InvalidSessionStateError(
                f"Session {session_id} is waiting for HITL response"
            )

        # Update status to processing
        await self._session_repo.update_status(session_id, SessionStatus.PROCESSING)

        try:
            # Execute agent loop
            result = await self._execute_agent_loop(session_id, content or session.goal)

            return {
                "session_id": session_id,
                "status": result["status"],
                "loop_count": result.get("loop_count", 0),
                "decision_type": result.get("decision_type"),
                "hitl_request": result.get("hitl_request"),
                "final_decision": result.get("final_decision")
            }

        except Exception as e:
            # Mark session as failed
            await self._session_repo.update_status(
                session_id,
                SessionStatus.FAILED,
                error_message=str(e)
            )
            raise

    async def submit_hitl_response(
        self,
        session_id: str,
        decision: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Submit a HITL response and resume processing.

        Args:
            session_id: Session ID
            decision: HITL decision/response

        Returns:
            Dict with processing result
        """
        session = await self.get_session(session_id)

        # Validate session state
        if session.status != SessionStatus.WAITING_HITL:
            raise InvalidSessionStateError(
                f"Session {session_id} is not waiting for HITL response"
            )

        # Record HITL response as observation
        await self._observation_service.record_hitl_response(
            session_id=session_id,
            loop_id=None,
            response=decision
        )

        # Clear HITL request and continue processing
        await self._session_repo.clear_hitl_request(session_id)

        # Continue processing with HITL response context
        return await self.process_message(session_id, f"HITL Response: {decision}")

    async def _execute_agent_loop(
        self,
        session_id: str,
        prompt: str
    ) -> Dict[str, Any]:
        """
        Execute the agent loop.

        This is a simplified implementation that runs the Claude agent
        and interprets the results for the Plan→Act→Observe→Critique→Decide flow.
        """
        session = await self.get_session(session_id)

        # Check loop limit
        if session.current_loop_count >= session.max_loop_count:
            raise LoopLimitExceededError(
                f"Session {session_id} has reached max loop count ({session.max_loop_count})"
            )

        # Create new loop record
        loop = AgentLoopEntity.create(
            session_id=session_id,
            iteration=session.current_loop_count
        )
        loop_id = await self._loop_repo.create(loop)

        # Increment loop count
        await self._session_repo.increment_loop_count(session_id)

        try:
            # Execute Claude agent
            async with GrowthAgentClient(max_turns=50) as client:
                client.set_session_context({
                    "session_id": session_id,
                    "loop_id": loop_id
                })

                result = await client.run_query(prompt)

            # Analyze agent response to determine decision
            decision_type, decision_data = self._analyze_agent_response(result)

            # Handle different decision types
            if decision_type == DecisionType.HITL_QUESTION:
                # Set HITL request and update status
                await self._session_repo.set_hitl_request(session_id, decision_data)
                return {
                    "status": SessionStatus.WAITING_HITL.value,
                    "loop_count": session.current_loop_count + 1,
                    "decision_type": decision_type.value,
                    "hitl_request": decision_data
                }

            elif decision_type == DecisionType.CONTINUE:
                # Need to continue processing
                return {
                    "status": SessionStatus.PROCESSING.value,
                    "loop_count": session.current_loop_count + 1,
                    "decision_type": decision_type.value
                }

            else:
                # Final decision (EXPERIMENT or INSTRUMENTATION_TODO)
                await self._session_repo.set_final_decision(session_id, decision_data)
                return {
                    "status": SessionStatus.COMPLETED.value,
                    "loop_count": session.current_loop_count + 1,
                    "decision_type": decision_type.value,
                    "final_decision": decision_data
                }

        except Exception as e:
            # Record error
            await self._observation_service.record_error(
                session_id=session_id,
                loop_id=loop_id,
                error_message=str(e)
            )
            raise

    def _analyze_agent_response(
        self,
        result: Dict[str, Any]
    ) -> tuple[DecisionType, Dict[str, Any]]:
        """
        Analyze agent response to determine decision type.

        This is a simplified heuristic-based analysis.
        In production, this could use structured outputs or additional LLM calls.
        """
        text_response = result.get("text_response", "").lower()

        # Check for HITL indicators
        hitl_indicators = [
            "need your input",
            "please confirm",
            "which option",
            "what do you think",
            "would you like",
            "should i proceed"
        ]
        if any(indicator in text_response for indicator in hitl_indicators):
            return DecisionType.HITL_QUESTION, {
                "question": result.get("text_response", ""),
                "context": "Agent is requesting human input"
            }

        # Check for experiment recommendation
        experiment_indicators = [
            "recommend testing",
            "suggest an experiment",
            "a/b test",
            "hypothesis",
            "expected impact"
        ]
        if any(indicator in text_response for indicator in experiment_indicators):
            return DecisionType.EXPERIMENT, {
                "recommendation": result.get("text_response", ""),
                "tool_calls": result.get("tool_calls", [])
            }

        # Check for instrumentation TODO
        instrumentation_indicators = [
            "need to track",
            "add tracking",
            "instrument",
            "missing data",
            "event tracking"
        ]
        if any(indicator in text_response for indicator in instrumentation_indicators):
            return DecisionType.INSTRUMENTATION_TODO, {
                "recommendation": result.get("text_response", ""),
                "tool_calls": result.get("tool_calls", [])
            }

        # Default to continue if no clear decision
        return DecisionType.CONTINUE, {}

    async def cancel_session(self, session_id: str) -> bool:
        """
        Cancel an active session.

        Args:
            session_id: Session ID to cancel

        Returns:
            True if cancelled successfully
        """
        session = await self.get_session(session_id)

        if session.is_terminal():
            raise InvalidSessionStateError(
                f"Cannot cancel session in terminal state: {session.status.value}"
            )

        return await self._session_repo.update_status(
            session_id,
            SessionStatus.CANCELLED
        )
