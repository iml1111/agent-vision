"""
FastAPI Application Factory

Creates and configures the FastAPI application instance.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from loguru import logger
from config import Config
from adapters.mongodb.client import MongoDBClient
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.external.slack_client import SlackClient
from adapters.external.notion_client import NotionClient
from .middleware import setup_middleware
from .exceptions import setup_exception_handlers
from .routes import register_routes


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for singleton initialization

    Initializes heavyweight resources once at startup:
    - MongoDBClient with connection pool (Lifespan Singleton Pattern)
    - OpenAI Embedding Client
    - External clients (Slack, Notion) - optional

    Resources are shared across all requests for efficiency.
    Note: Allowlist configuration is now integrated into Config.
    """
    config = app.state.config

    # Initialize MongoDB client singleton with connection pool settings
    app.state.db_client = MongoDBClient(
        uri=config.mongodb_uri,
        db_name=config.mongodb_name,
        max_pool_size=50,
        min_pool_size=10,
        max_idle_time_ms=60000
    )

    # Initialize OpenAI Embedding Client
    app.state.openai_client = OpenAIEmbeddingClient(
        api_key=config.openai_api_key
    )
    logger.info("OpenAI Embedding Client initialized")

    # Log Allowlist Configuration (integrated into Config)
    logger.info(
        f"Allowlist initialized: "
        f"{len(config.slack_channels)} Slack channels, "
        f"{len(config.notion_databases)} Notion databases, "
        f"{len(config.notion_pages)} Notion pages"
    )

    # Initialize External Clients (optional based on config)
    app.state.slack_client = None
    app.state.notion_client = None

    if config.slack_bot_token:
        app.state.slack_client = SlackClient(bot_token=config.slack_bot_token)
        logger.info("Slack Client initialized")

    if config.notion_api_key:
        app.state.notion_client = NotionClient(api_key=config.notion_api_key)
        logger.info("Notion Client initialized")

    # Initialize Agent Tool Dependencies
    _initialize_agent_tool_dependencies(app)

    yield

    # Cleanup
    app.state.db_client.close()
    logger.info("Database connection closed")


def _initialize_agent_tool_dependencies(app: FastAPI):
    """Initialize dependencies for agent tools and hooks"""
    from adapters.agent_tools.slack_tool import set_slack_dependencies
    from adapters.agent_tools.notion_tool import set_notion_dependencies
    from adapters.agent_tools.growth_memory_tool import set_growth_memory_dependencies
    from adapters.agent_hooks.pre_tool_use import set_hook_dependencies
    from adapters.mongodb.collections.growth_memory_adapter import GrowthMemoryAdapter
    from adapters.repositories.mongodb.growth_memory import MongoGrowthMemoryRepository

    # Set Slack tool dependencies
    set_slack_dependencies(
        slack_client=app.state.slack_client,
        config=app.state.config
    )

    # Set Notion tool dependencies
    set_notion_dependencies(
        notion_client=app.state.notion_client,
        config=app.state.config
    )

    # Set Growth Memory tool dependencies
    growth_memory_repo = MongoGrowthMemoryRepository(
        GrowthMemoryAdapter(app.state.db_client.db)
    )
    set_growth_memory_dependencies(
        growth_memory_repo=growth_memory_repo,
        embedding_client=app.state.openai_client
    )

    # Set hook dependencies
    set_hook_dependencies(config=app.state.config)

    logger.info("Agent tool dependencies initialized")


def create_app(config: Config = None) -> FastAPI:
    """
    Create and configure FastAPI application

    Args:
        config: Application configuration instance (optional, creates new if None)
    """
    if config is None:
        config = Config()

    is_dev = config.environment == "development"

    app = FastAPI(
        title=config.app_name,
        description=config.description,
        version=config.version,
        contact={
            "name": config.contact_name,
            "url": config.contact_url,
            "email": config.contact_email,
        },
        docs_url="/docs" if is_dev else None,
        redoc_url="/redoc" if is_dev else None,
        openapi_url="/openapi.json" if is_dev else None,
        lifespan=lifespan
    )

    # Store config in app state for dependency injection
    app.state.config = config

    # Setup components
    setup_middleware(app)
    setup_exception_handlers(app)
    register_routes(app)

    return app


# Default app instance for uvicorn
# For testing or custom configs, use create_app(config) factory instead
app = create_app()
