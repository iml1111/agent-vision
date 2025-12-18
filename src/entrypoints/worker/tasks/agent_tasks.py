"""
Agent Processing Tasks

Task handlers for async agent response processing via SQS worker.
"""
from typing import Dict, Any
from logging_config import get_logger

from entrypoints.worker.task_registry import task
from entrypoints.worker.dependencies import WorkerDependencies
from service_layer.application.agent_orchestration_service import AgentOrchestrationService

logger = get_logger(__name__)


@task
async def process_agent_response(data: Dict[str, Any]) -> None:
    """
    Process agent response for a user message.

    Called by SQS worker after API enqueues a message.
    Executes the heavy-lifting agent run and saves the response.

    Args:
        data: Task payload containing:
            - session_id: str - Session identifier
            - user_message_id: str - ID of the user message to respond to
    """
    session_id = data["session_id"]
    user_message_id = data["user_message_id"]

    logger.info(
        f"Processing agent response: session_id={session_id}, "
        f"user_message_id={user_message_id}"
    )

    # Get dependencies
    db_client = WorkerDependencies.get_db_client()
    sqs_producer = WorkerDependencies.get_sqs_producer()
    config = WorkerDependencies.get_config()
    eventlog_adapter = WorkerDependencies.get_eventlog_adapter()
    slack_client = WorkerDependencies.get_slack_client()
    notion_client = WorkerDependencies.get_notion_client()

    # Create service instance with agent tool dependencies
    service = AgentOrchestrationService(
        db_client=db_client,
        eventlog_adapter=eventlog_adapter,
        slack_client=slack_client,
        notion_client=notion_client,
        config=config
    )

    # Execute agent response (handles its own error recovery)
    # Passes sqs_producer for enqueueing memory extraction on session archive
    await service.execute_agent_response(
        session_id=session_id,
        user_message_id=user_message_id,
        sqs_producer=sqs_producer
    )
