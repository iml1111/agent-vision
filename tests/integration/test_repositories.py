"""
Integration Tests for MongoDB Repositories

Tests repository operations with real MongoDB connection.
"""
import pytest

from domain.entities.agent_session import AgentSessionEntity
from domain.entities.agent_loop import AgentLoopEntity
from domain.entities.observation import ObservationEntity
from domain.value_objects.agent_enums import (
    SessionStatus,
    LoopPhase,
    ObservationType,
)
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from adapters.mongodb.collections.agent_loop_adapter import AgentLoopAdapter
from adapters.mongodb.collections.observation_adapter import ObservationAdapter
from adapters.repositories.mongodb.agent_session import MongoAgentSessionRepository
from adapters.repositories.mongodb.agent_loop import MongoAgentLoopRepository
from adapters.repositories.mongodb.observation import MongoObservationRepository


class TestAgentSessionRepository:
    """Tests for AgentSessionRepository."""

    @pytest.fixture
    def repo(self, db_client):
        """Create repository instance."""
        adapter = AgentSessionAdapter(db_client.db)
        return MongoAgentSessionRepository(adapter)

    @pytest.mark.asyncio
    async def test_create_and_get_session(self, repo, sample_session_data):
        """Test creating and retrieving a session."""
        # Create session
        session = AgentSessionEntity.create(
            goal=sample_session_data["goal"],
            context=sample_session_data["context"],
            max_loop_count=10
        )

        session_id = await repo.create(session)
        assert session_id is not None

        # Retrieve session
        retrieved = await repo.get_by_id(session_id)
        assert retrieved is not None
        assert retrieved.id == session_id
        assert retrieved.goal == sample_session_data["goal"]
        assert retrieved.status == SessionStatus.CREATED

    @pytest.mark.asyncio
    async def test_update_status(self, repo, sample_session_data):
        """Test updating session status."""
        session = AgentSessionEntity.create(
            goal=sample_session_data["goal"],
            context=sample_session_data["context"]
        )
        session_id = await repo.create(session)

        # Update status
        result = await repo.update_status(session_id, SessionStatus.PROCESSING)
        assert result is True

        # Verify update
        updated = await repo.get_by_id(session_id)
        assert updated.status == SessionStatus.PROCESSING

    @pytest.mark.asyncio
    async def test_increment_loop_count(self, repo, sample_session_data):
        """Test incrementing loop count."""
        session = AgentSessionEntity.create(
            goal=sample_session_data["goal"],
            context=sample_session_data["context"]
        )
        session_id = await repo.create(session)

        # Increment loop count
        await repo.increment_loop_count(session_id)
        await repo.increment_loop_count(session_id)

        # Verify
        updated = await repo.get_by_id(session_id)
        assert updated.current_loop_count == 2

    @pytest.mark.asyncio
    async def test_set_hitl_request(self, repo, sample_session_data):
        """Test setting HITL request."""
        session = AgentSessionEntity.create(
            goal=sample_session_data["goal"],
            context=sample_session_data["context"]
        )
        session_id = await repo.create(session)

        hitl_request = {
            "question": "Which approach do you prefer?",
            "options": ["A", "B", "C"]
        }

        result = await repo.set_hitl_request(session_id, hitl_request)
        assert result is True

        updated = await repo.get_by_id(session_id)
        assert updated.hitl_request == hitl_request
        assert updated.status == SessionStatus.WAITING_HITL

    @pytest.mark.asyncio
    async def test_set_final_decision(self, repo, sample_session_data):
        """Test setting final decision."""
        session = AgentSessionEntity.create(
            goal=sample_session_data["goal"],
            context=sample_session_data["context"]
        )
        session_id = await repo.create(session)

        final_decision = {
            "recommendation": "Implement onboarding tutorial",
            "expected_impact": "15% improvement"
        }

        result = await repo.set_final_decision(session_id, final_decision)
        assert result is True

        updated = await repo.get_by_id(session_id)
        assert updated.final_decision == final_decision
        assert updated.status == SessionStatus.COMPLETED


class TestAgentLoopRepository:
    """Tests for AgentLoopRepository."""

    @pytest.fixture
    def repo(self, db_client):
        """Create repository instance."""
        adapter = AgentLoopAdapter(db_client.db)
        return MongoAgentLoopRepository(adapter)

    @pytest.mark.asyncio
    async def test_create_and_get_loop(self, repo):
        """Test creating and retrieving a loop."""
        loop = AgentLoopEntity.create(
            session_id="test_session_123",
            iteration=0
        )

        loop_id = await repo.create(loop)
        assert loop_id is not None

        retrieved = await repo.get_by_id(loop_id)
        assert retrieved is not None
        assert retrieved.session_id == "test_session_123"
        assert retrieved.iteration == 0

    @pytest.mark.asyncio
    async def test_get_by_session_id(self, repo):
        """Test retrieving loops by session ID."""
        session_id = "test_session_456"

        # Create multiple loops
        for i in range(3):
            loop = AgentLoopEntity.create(session_id=session_id, iteration=i)
            await repo.create(loop)

        loops = await repo.get_by_session_id(session_id)
        assert len(loops) == 3
        assert all(loop.session_id == session_id for loop in loops)

    @pytest.mark.asyncio
    async def test_update_phase(self, repo):
        """Test updating loop phase."""
        loop = AgentLoopEntity.create(
            session_id="test_session_789",
            iteration=0
        )
        loop_id = await repo.create(loop)

        # Update phase with output
        result = await repo.update_phase(
            loop_id,
            LoopPhase.ACT,
            {"actions": ["tool_call_1", "tool_call_2"]}
        )
        assert result is True

        updated = await repo.get_by_id(loop_id)
        assert updated.current_phase == LoopPhase.ACT


class TestObservationRepository:
    """Tests for ObservationRepository."""

    @pytest.fixture
    def repo(self, db_client):
        """Create repository instance."""
        adapter = ObservationAdapter(db_client.db)
        return MongoObservationRepository(adapter)

    @pytest.mark.asyncio
    async def test_create_and_get_observation(self, repo, sample_observation_data):
        """Test creating and retrieving an observation."""
        observation = ObservationEntity.create(
            session_id="test_session",
            loop_id="test_loop",
            observation_type=ObservationType.TOOL_RESULT,
            content=sample_observation_data["content"],
            tool_name=sample_observation_data["tool_name"]
        )

        obs_id = await repo.create(observation)
        assert obs_id is not None

        retrieved = await repo.get_by_id(obs_id)
        assert retrieved is not None
        assert retrieved.session_id == "test_session"

    @pytest.mark.asyncio
    async def test_get_by_session_id(self, repo):
        """Test retrieving observations by session ID."""
        session_id = "obs_session_123"

        # Create multiple observations
        for i in range(5):
            obs = ObservationEntity.create(
                session_id=session_id,
                loop_id=f"loop_{i}",
                observation_type=ObservationType.TOOL_RESULT,
                content={"index": i}
            )
            await repo.create(obs)

        observations = await repo.get_by_session_id(session_id, limit=10)
        assert len(observations) == 5

    @pytest.mark.asyncio
    async def test_count_by_session_id(self, repo):
        """Test counting observations by session ID."""
        session_id = "count_session_123"

        for i in range(3):
            obs = ObservationEntity.create(
                session_id=session_id,
                loop_id=f"loop_{i}",
                observation_type=ObservationType.TOOL_RESULT,
                content={"index": i}
            )
            await repo.create(obs)

        count = await repo.count_by_session_id(session_id)
        assert count == 3
