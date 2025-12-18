"""
Worker Dependencies

Dependency injection for worker components and task handlers
"""
from typing import Optional, Callable

from config import Config, SQS_WAIT_TIME_SECONDS
from adapters.anthropic.summarization_client import ClaudeSummarizationClient
from adapters.aws import SQSConsumerAdapter, SQSProducerAdapter
from adapters.external.notion_client import NotionClient
from adapters.external.slack_client import SlackClient
from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.eventlog_adapter import EventLogAdapter
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.uow.mongo_unit_of_work import MongoUnitOfWork
from domain.ports.unit_of_work import AbstractUnitOfWork


def get_sqs_consumer(config: Config) -> SQSConsumerAdapter:
    """
    Get SQS consumer adapter

    Args:
        config: Application configuration
    """
    return SQSConsumerAdapter(
        queue_url=config.sqs_queue_url,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
        region_name=config.aws_region,
        wait_time_seconds=SQS_WAIT_TIME_SECONDS
    )


class WorkerDependencies:
    """
    Global dependency container for task handlers

    Initialized once at worker startup, shared across all task handlers.
    Similar to FastAPI's Depends pattern but for background workers.

    Example:
        # In worker startup
        WorkerDependencies.initialize(config)

        # In task handler
        db_client = WorkerDependencies.get_db_client()
    """

    _config: Optional[Config] = None
    _db_client: Optional[MongoDBClient] = None
    _embedding_client: Optional[OpenAIEmbeddingClient] = None
    _summarization_client: Optional[ClaudeSummarizationClient] = None
    _sqs_producer: Optional[SQSProducerAdapter] = None
    _eventlog_adapter: Optional[EventLogAdapter] = None
    _slack_client: Optional[SlackClient] = None
    _notion_client: Optional[NotionClient] = None

    @classmethod
    def initialize(cls, config: Config) -> None:
        """
        Initialize all dependencies

        Args:
            config: Config instance
        """
        cls._config = config
        cls._db_client = MongoDBClient(
            uri=config.mongodb_uri,
            db_name=config.mongodb_name
        )
        cls._embedding_client = OpenAIEmbeddingClient(
            api_key=config.openai_api_key
        )
        cls._summarization_client = ClaudeSummarizationClient(
            api_key=config.anthropic_api_key
        )
        cls._sqs_producer = SQSProducerAdapter(
            queue_url=config.sqs_queue_url,
            aws_access_key_id=config.aws_access_key_id,
            aws_secret_access_key=config.aws_secret_access_key,
            region_name=config.aws_region
        )

        # Agent tool dependencies
        cls._eventlog_adapter = EventLogAdapter(cls._db_client.db)

        if config.slack_bot_token:
            cls._slack_client = SlackClient(bot_token=config.slack_bot_token)

        if config.notion_api_key:
            cls._notion_client = NotionClient(api_key=config.notion_api_key)

    @classmethod
    def get_config(cls) -> Config:
        """Get config instance"""
        if cls._config is None:
            raise RuntimeError("Dependencies not initialized. Call initialize() first.")
        return cls._config

    @classmethod
    def get_db_client(cls) -> MongoDBClient:
        """Get MongoDB client instance"""
        if cls._db_client is None:
            raise RuntimeError("Dependencies not initialized. Call initialize() first.")
        return cls._db_client

    @classmethod
    def get_embedding_client(cls) -> OpenAIEmbeddingClient:
        """Get OpenAI embedding client instance"""
        if cls._embedding_client is None:
            raise RuntimeError("Dependencies not initialized. Call initialize() first.")
        return cls._embedding_client

    @classmethod
    def get_summarization_client(cls) -> ClaudeSummarizationClient:
        """Get Claude summarization client instance"""
        if cls._summarization_client is None:
            raise RuntimeError("Dependencies not initialized. Call initialize() first.")
        return cls._summarization_client

    @classmethod
    def get_sqs_producer(cls) -> SQSProducerAdapter:
        """Get SQS producer instance for enqueueing tasks"""
        if cls._sqs_producer is None:
            raise RuntimeError("Dependencies not initialized. Call initialize() first.")
        return cls._sqs_producer

    @classmethod
    def get_eventlog_adapter(cls) -> EventLogAdapter:
        """Get EventLog adapter for analytics tools"""
        if cls._eventlog_adapter is None:
            raise RuntimeError("Dependencies not initialized. Call initialize() first.")
        return cls._eventlog_adapter

    @classmethod
    def get_slack_client(cls) -> Optional[SlackClient]:
        """Get Slack client (None if not configured)"""
        return cls._slack_client

    @classmethod
    def get_notion_client(cls) -> Optional[NotionClient]:
        """Get Notion client (None if not configured)"""
        return cls._notion_client

    @classmethod
    def get_uow_factory(cls) -> Callable[[], AbstractUnitOfWork]:
        """
        Get UnitOfWork factory

        Returns a factory function that creates MongoUnitOfWork instances
        for atomic operations across multiple repositories.

        Returns:
            Factory function that creates MongoUnitOfWork instances
        """
        db_client = cls.get_db_client()

        def create_uow() -> AbstractUnitOfWork:
            return MongoUnitOfWork(db_client)

        return create_uow

    @classmethod
    def clear(cls) -> None:
        """Clear all dependencies (for testing)"""
        if cls._db_client:
            cls._db_client.close()
        cls._config = None
        cls._db_client = None
        cls._embedding_client = None
        cls._summarization_client = None
        cls._sqs_producer = None
        cls._eventlog_adapter = None
        cls._slack_client = None
        cls._notion_client = None
