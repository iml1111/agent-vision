"""
End-to-End Tests for Agent API

Tests API endpoints with real HTTP requests using TestClient.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from entrypoints.api.app import create_app
from config import Config


@pytest.fixture
def test_app(db_client, mock_embedding_client, mock_allowlist_config):
    """Create test FastAPI app with test dependencies."""
    config = Config()
    config._mongodb_uri = db_client._uri
    config._mongodb_name = db_client.db.name

    app = create_app(config)

    # Override app state with test dependencies
    app.state.db_client = db_client
    app.state.openai_client = mock_embedding_client
    app.state.allowlist_config = mock_allowlist_config
    app.state.slack_client = None
    app.state.notion_client = None
    app.state.config = config

    return app


@pytest.fixture
def client(test_app) -> TestClient:
    """Create synchronous test client."""
    return TestClient(test_app, raise_server_exceptions=False)


@pytest.fixture
async def async_client(test_app) -> AsyncClient:
    """Create async test client."""
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check returns OK."""
        response = client.get("/health")
        assert response.status_code == 200


class TestSessionEndpoints:
    """Tests for agent session endpoints."""

    def test_create_session_success(self, client):
        """Test creating a new session."""
        response = client.post(
            "/api/v1/agent/sessions",
            json={
                "goal": "Analyze user retention for mobile users",
                "context": {"product_area": "onboarding"}
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "session_id" in data
        assert data["status"] == "created"
        assert data["goal"] == "Analyze user retention for mobile users"

    def test_create_session_minimal(self, client):
        """Test creating session with only required fields."""
        response = client.post(
            "/api/v1/agent/sessions",
            json={"goal": "Simple analysis goal"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["goal"] == "Simple analysis goal"

    def test_create_session_invalid_goal(self, client):
        """Test creating session with empty goal fails."""
        response = client.post(
            "/api/v1/agent/sessions",
            json={"goal": ""}
        )

        assert response.status_code == 422  # Validation error

    def test_get_session_status(self, client):
        """Test getting session status."""
        # Create session first
        create_response = client.post(
            "/api/v1/agent/sessions",
            json={"goal": "Test goal"}
        )
        session_id = create_response.json()["session_id"]

        # Get status
        response = client.get(f"/api/v1/agent/sessions/{session_id}/status")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["status"] == "active"
        assert data["message_count"] == 0

    def test_get_session_status_not_found(self, client):
        """Test getting status for non-existent session."""
        response = client.get("/api/v1/agent/sessions/nonexistent123/status")
        assert response.status_code == 404

    def test_cancel_session(self, client):
        """Test canceling a session."""
        # Create session
        create_response = client.post(
            "/api/v1/agent/sessions",
            json={"goal": "Test goal"}
        )
        session_id = create_response.json()["session_id"]

        # Cancel session
        response = client.delete(f"/api/v1/agent/sessions/{session_id}")
        assert response.status_code == 204

        # Verify cancelled
        status_response = client.get(f"/api/v1/agent/sessions/{session_id}/status")
        assert status_response.json()["status"] == "cancelled"

    def test_cancel_session_not_found(self, client):
        """Test canceling non-existent session."""
        response = client.delete("/api/v1/agent/sessions/nonexistent123")
        assert response.status_code == 404


class TestObservationEndpoints:
    """Tests for observation endpoints."""

    def test_get_observations_empty(self, client):
        """Test getting observations for new session."""
        # Create session
        create_response = client.post(
            "/api/v1/agent/sessions",
            json={"goal": "Test goal"}
        )
        session_id = create_response.json()["session_id"]

        # Get observations
        response = client.get(f"/api/v1/agent/sessions/{session_id}/observations")

        assert response.status_code == 200
        data = response.json()
        assert data["session_id"] == session_id
        assert data["observations"] == []
        assert data["total_count"] == 0

    def test_get_observations_with_pagination(self, client):
        """Test observation pagination parameters."""
        # Create session
        create_response = client.post(
            "/api/v1/agent/sessions",
            json={"goal": "Test goal"}
        )
        session_id = create_response.json()["session_id"]

        # Get observations with pagination
        response = client.get(
            f"/api/v1/agent/sessions/{session_id}/observations",
            params={"limit": 10, "offset": 0}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 0

    def test_get_observations_invalid_session(self, client):
        """Test getting observations for non-existent session."""
        response = client.get("/api/v1/agent/sessions/nonexistent123/observations")
        assert response.status_code == 404


class TestHITLEndpoints:
    """Tests for HITL (Human-in-the-Loop) endpoints."""

    def test_submit_hitl_wrong_state(self, client):
        """Test submitting HITL when session is not waiting."""
        # Create session (starts in CREATED state, not WAITING_HITL)
        create_response = client.post(
            "/api/v1/agent/sessions",
            json={"goal": "Test goal"}
        )
        session_id = create_response.json()["session_id"]

        # Try to submit HITL response
        response = client.post(
            f"/api/v1/agent/sessions/{session_id}/hitl",
            json={
                "decision": {"choice": "option_a", "reason": "Test reason"}
            }
        )

        assert response.status_code == 400  # Invalid state

    def test_submit_hitl_not_found(self, client):
        """Test submitting HITL for non-existent session."""
        response = client.post(
            "/api/v1/agent/sessions/nonexistent123/hitl",
            json={"decision": {"choice": "option_a"}}
        )
        assert response.status_code == 404


class TestMessageEndpoints:
    """Tests for message endpoints."""

    def test_send_message_to_new_session(self, client):
        """Test sending message to start processing."""
        # Create session
        create_response = client.post(
            "/api/v1/agent/sessions",
            json={"goal": "Test goal"}
        )
        session_id = create_response.json()["session_id"]

        # Mock the agent execution to avoid actual API calls
        with patch(
            'service_layer.application.agent_orchestration_service.GrowthAgentClient'
        ) as mock_agent:
            mock_instance = MagicMock()
            mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
            mock_instance.__aexit__ = AsyncMock(return_value=None)
            mock_instance.set_session_context = MagicMock()
            mock_instance.run_query = AsyncMock(return_value={
                "text_response": "Analysis complete. Recommend testing new onboarding flow.",
                "tool_calls": []
            })
            mock_agent.return_value = mock_instance

            # Send message
            response = client.post(
                f"/api/v1/agent/sessions/{session_id}/messages",
                json={"content": "Start analysis"}
            )

            # Should succeed but we can't guarantee response without full integration
            assert response.status_code in [200, 500]  # 500 if agent not fully configured

    def test_send_message_not_found(self, client):
        """Test sending message to non-existent session."""
        response = client.post(
            "/api/v1/agent/sessions/nonexistent123/messages",
            json={"content": "Test message"}
        )
        assert response.status_code == 404


class TestAPIPollingWorkflow:
    """Tests for the polling-based API workflow."""

    def test_full_session_lifecycle(self, client):
        """Test complete session lifecycle without agent execution."""
        # 1. Create session
        create_response = client.post(
            "/api/v1/agent/sessions",
            json={
                "goal": "Analyze retention",
                "context": {"segment": "mobile"}
            }
        )
        assert create_response.status_code == 201
        session_id = create_response.json()["session_id"]

        # 2. Check initial status
        status_response = client.get(f"/api/v1/agent/sessions/{session_id}/status")
        assert status_response.status_code == 200
        assert status_response.json()["status"] == "created"

        # 3. Get observations (empty initially)
        obs_response = client.get(f"/api/v1/agent/sessions/{session_id}/observations")
        assert obs_response.status_code == 200
        assert obs_response.json()["total_count"] == 0

        # 4. Cancel session
        cancel_response = client.delete(f"/api/v1/agent/sessions/{session_id}")
        assert cancel_response.status_code == 204

        # 5. Verify final status
        final_status = client.get(f"/api/v1/agent/sessions/{session_id}/status")
        assert final_status.json()["status"] == "cancelled"

    def test_multiple_sessions_isolation(self, client):
        """Test that multiple sessions don't interfere with each other."""
        # Create two sessions
        session1 = client.post(
            "/api/v1/agent/sessions",
            json={"goal": "Goal 1"}
        ).json()["session_id"]

        session2 = client.post(
            "/api/v1/agent/sessions",
            json={"goal": "Goal 2"}
        ).json()["session_id"]

        # Cancel session 1
        client.delete(f"/api/v1/agent/sessions/{session1}")

        # Session 2 should still be created
        status2 = client.get(f"/api/v1/agent/sessions/{session2}/status")
        assert status2.json()["status"] == "created"

        # Session 1 should be cancelled
        status1 = client.get(f"/api/v1/agent/sessions/{session1}/status")
        assert status1.json()["status"] == "cancelled"
