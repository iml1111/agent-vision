"""
Integration Tests for Service Layer

Tests service operations with real MongoDB connection.
"""
import pytest

from domain.value_objects.agent_enums import (
    SessionStatus,
    ObservationType,
)
from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
)
from service_layer.application.agent_orchestration_service import AgentOrchestrationService
from service_layer.application.observation_service import ObservationService


class TestObservationService:
    """Tests for ObservationService."""

    @pytest.fixture
    def service(self, db_client):
        """Create service instance."""
        return ObservationService(db_client)

    @pytest.mark.asyncio
    async def test_record_tool_result(self, service):
        """Test recording a tool result observation."""
        session_id = "test_session_obs"
        loop_id = "test_loop_obs"

        await service.record_tool_result(
            session_id=session_id,
            loop_id=loop_id,
            tool_name="funnel_analysis",
            result={"conversion_rate": 0.45},
            is_error=False
        )

        # Retrieve and verify
        observations = await service.get_observations(session_id)
        assert len(observations) == 1
        assert observations[0].tool_name == "funnel_analysis"

    @pytest.mark.asyncio
    async def test_record_error(self, service):
        """Test recording an error observation."""
        session_id = "test_session_error"
        loop_id = "test_loop_error"

        await service.record_error(
            session_id=session_id,
            loop_id=loop_id,
            error_message="Connection timeout"
        )

        observations = await service.get_observations(session_id)
        assert len(observations) == 1
        assert observations[0].is_error is True
        assert observations[0].observation_type == ObservationType.ERROR

    @pytest.mark.asyncio
    async def test_record_hitl_response(self, service):
        """Test recording HITL response observation."""
        session_id = "test_session_hitl"

        await service.record_hitl_response(
            session_id=session_id,
            loop_id=None,
            response={"choice": "option_a", "reason": "Better UX"}
        )

        observations = await service.get_observations(session_id)
        assert len(observations) == 1
        assert observations[0].observation_type == ObservationType.HITL_RESPONSE

    @pytest.mark.asyncio
    async def test_get_session_summary(self, service):
        """Test getting session observation summary."""
        session_id = "test_session_summary"

        # Create various observations
        await service.record_tool_result(
            session_id=session_id,
            loop_id="loop1",
            tool_name="funnel_analysis",
            result={"data": "test"},
            is_error=False
        )
        await service.record_tool_result(
            session_id=session_id,
            loop_id="loop1",
            tool_name="segment_analysis",
            result={"segments": []},
            is_error=False
        )
        await service.record_error(
            session_id=session_id,
            loop_id="loop1",
            error_message="Test error"
        )

        summary = await service.get_session_summary(session_id)

        assert summary["total_observations"] == 3
        assert summary["error_count"] == 1
        assert summary["tool_call_count"] == 2
        assert "funnel_analysis" in summary["tools_used"]


class TestAgentOrchestrationService:
    """Tests for AgentOrchestrationService."""

    @pytest.fixture
    def service(self, db_client, mock_embedding_client):
        """Create service instance."""
        return AgentOrchestrationService(
            db_client=db_client,
            embedding_client=mock_embedding_client,
            max_loop_count=10
        )

    @pytest.mark.asyncio
    async def test_create_session(self, service, sample_session_data):
        """Test creating an agent session."""
        session = await service.create_session(
            goal=sample_session_data["goal"],
            context=sample_session_data["context"]
        )

        assert session is not None
        assert session.id is not None
        assert session.goal == sample_session_data["goal"]
        assert session.status == SessionStatus.CREATED

    @pytest.mark.asyncio
    async def test_get_session(self, service, sample_session_data):
        """Test retrieving a session."""
        created = await service.create_session(
            goal=sample_session_data["goal"]
        )

        retrieved = await service.get_session(created.id)
        assert retrieved.id == created.id
        assert retrieved.goal == created.goal

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, service):
        """Test retrieving non-existent session raises error."""
        with pytest.raises(AgentSessionNotFoundError):
            await service.get_session("nonexistent_id")

    @pytest.mark.asyncio
    async def test_get_session_status(self, service, sample_session_data):
        """Test getting detailed session status."""
        session = await service.create_session(
            goal=sample_session_data["goal"]
        )

        status = await service.get_session_status(session.id)

        assert status.session_id == session.id
        assert status.status == SessionStatus.ACTIVE.value
        assert status.message_count == 0

    @pytest.mark.asyncio
    async def test_cancel_session(self, service, sample_session_data):
        """Test canceling a session."""
        session = await service.create_session(
            goal=sample_session_data["goal"]
        )

        result = await service.cancel_session(session.id)
        assert result is True

        status = await service.get_session_status(session.id)
        assert status.status == SessionStatus.ARCHIVED.value

    @pytest.mark.asyncio
    async def test_cancel_completed_session_fails(self, service, sample_session_data):
        """Test canceling a completed session raises error."""
        session = await service.create_session(
            goal=sample_session_data["goal"]
        )

        # Manually complete the session
        await service._session_repo.update_status(session.id, SessionStatus.COMPLETED)

        with pytest.raises(InvalidSessionStateError):
            await service.cancel_session(session.id)

    @pytest.mark.asyncio
    async def test_process_message_validates_state(self, service, sample_session_data):
        """Test that process_message validates session state."""
        session = await service.create_session(
            goal=sample_session_data["goal"]
        )

        # Set to WAITING_HITL
        await service._session_repo.set_hitl_request(
            session.id,
            {"question": "Test?"}
        )

        with pytest.raises(InvalidSessionStateError):
            await service.process_message(session.id, "test message")

    @pytest.mark.asyncio
    async def test_submit_hitl_response_validates_state(self, service, sample_session_data):
        """Test that HITL submission validates session state."""
        session = await service.create_session(
            goal=sample_session_data["goal"]
        )

        # Session is not in WAITING_HITL state
        with pytest.raises(InvalidSessionStateError):
            await service.submit_hitl_response(
                session.id,
                {"choice": "option_a"}
            )
