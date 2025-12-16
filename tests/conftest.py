"""
Pytest Configuration and Fixtures

Provides shared fixtures for integration and unit tests.
"""
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from config import Config
from adapters.mongodb.client import MongoDBClient
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from config.allowlist import AllowlistConfig


# Event loop fixture for async tests
@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_config() -> Config:
    """Create test configuration."""
    # Set test environment variables
    os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27017")
    os.environ.setdefault("MONGODB_NAME", "agent_vision_test")
    os.environ.setdefault("OPENAI_API_KEY", "test-key")
    os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
    os.environ.setdefault("ENVIRONMENT", "test")

    return Config()


@pytest.fixture(scope="function")
async def db_client(test_config: Config) -> AsyncGenerator[MongoDBClient, None]:
    """Create MongoDB client for tests."""
    client = MongoDBClient(
        uri=test_config.mongodb_uri,
        db_name=f"{test_config.mongodb_name}_test_{datetime.now().strftime('%Y%m%d%H%M%S')}",
        max_pool_size=5,
        min_pool_size=1,
    )

    yield client

    # Cleanup: drop test database
    await client._client.drop_database(client.db.name)
    client.close()


@pytest.fixture
def mock_embedding_client() -> MagicMock:
    """Create mock OpenAI embedding client."""
    client = MagicMock(spec=OpenAIEmbeddingClient)

    # Generate mock embedding (1536 dimensions)
    mock_embedding = [0.1] * 1536

    client.generate_embedding = AsyncMock(return_value=mock_embedding)
    client.generate_embeddings = AsyncMock(
        side_effect=lambda texts: [mock_embedding for _ in texts]
    )

    return client


@pytest.fixture
def mock_allowlist_config() -> AllowlistConfig:
    """Create allowlist config with test channels/databases."""
    # Set test allowlist environment variables
    os.environ["SLACK_CHANNEL_ALLOWLIST"] = '[{"channel_id": "C123", "channel_name": "test-channel"}]'
    os.environ["NOTION_DATABASE_ALLOWLIST"] = '[{"database_id": "db123", "database_name": "Test DB"}]'
    os.environ["NOTION_PAGE_ALLOWLIST"] = '[{"page_id": "page123", "page_title": "Test Page"}]'

    return AllowlistConfig()


@pytest.fixture
def sample_session_data() -> dict:
    """Sample data for creating agent sessions."""
    return {
        "goal": "Analyze user retention for mobile users",
        "context": {
            "product_area": "onboarding",
            "target_metric": "d7_retention",
            "user_segment": "mobile"
        }
    }


@pytest.fixture
def sample_observation_data() -> dict:
    """Sample data for creating observations."""
    return {
        "observation_type": "tool_result",
        "content": {
            "tool": "funnel_analysis",
            "result": {"conversion_rate": 0.45}
        },
        "tool_name": "funnel_analysis",
        "is_error": False
    }


@pytest.fixture
def sample_growth_memory_data() -> dict:
    """Sample data for creating growth memories."""
    return {
        "content": "Mobile users show 15% higher D7 retention when completing onboarding tutorial",
        "memory_type": "insight",
        "tags": ["retention", "mobile", "onboarding"],
        "metadata": {
            "confidence": 0.85,
            "data_points": 10000
        }
    }
