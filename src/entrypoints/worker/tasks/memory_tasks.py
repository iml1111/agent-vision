"""
Memory Processing Tasks

Task handlers for async GrowthMemory extraction via SQS worker.
"""
from typing import Dict, Any
from logging_config import get_logger

from entrypoints.worker.task_registry import task
from entrypoints.worker.dependencies import WorkerDependencies
from service_layer.application.growth_memory_service import GrowthMemoryService
from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
    SummarizationError,
)

logger = get_logger(__name__)


@task
async def archive_session_to_memory(data: Dict[str, Any]) -> None:
    """
    Archive session conversation to GrowthMemory.

    Called by SQS worker after session is archived.
    Extracts structured insights and creates searchable memory document.

    Pipeline:
    1. Load session and all messages
    2. Call Claude API for structured summarization (6 units)
    3. Generate embedding for semantic search (Problem + Bottleneck)
    4. Save GrowthMemory document

    Args:
        data: Task payload containing:
            - session_id: str - Session to archive to memory

    Note:
        - Only archived sessions can have memories created
        - Duplicate memory creation is prevented (idempotent)
        - Session not found or not archived errors are logged but not retried
        - Summarization errors will cause retry via SQS visibility timeout
    """
    session_id = data["session_id"]

    logger.info(f"Archiving session to memory: session_id={session_id}")

    # Get dependencies
    db_client = WorkerDependencies.get_db_client()
    summarization_client = WorkerDependencies.get_summarization_client()
    embedding_client = WorkerDependencies.get_embedding_client()

    # Create service instance
    service = GrowthMemoryService(
        db_client=db_client,
        summarization_client=summarization_client,
        embedding_client=embedding_client
    )

    try:
        memory_id = await service.create_memory_from_session(session_id)
        logger.info(
            f"Successfully created GrowthMemory: memory_id={memory_id}, "
            f"session_id={session_id}"
        )

    except AgentSessionNotFoundError as e:
        # Session doesn't exist - permanent failure, don't retry
        logger.error(f"Session not found, skipping memory creation: {e}")
        return

    except InvalidSessionStateError as e:
        # Session not archived yet - permanent failure, don't retry
        logger.error(f"Session not in archived state, skipping memory creation: {e}")
        return

    except SummarizationError as e:
        # Summarization failed - retry via SQS
        logger.error(f"Summarization failed, will retry: {e}")
        raise

    except Exception as e:
        # Unexpected error - retry via SQS
        logger.error(f"Unexpected error during memory creation: {e}")
        raise
