"""
Agent API Routes

REST API endpoints for conversational agent session management.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from adapters.aws.sqs_producer import SQSProducerAdapter
from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
)
from entrypoints.api.schemas.agent import (
    MessageEnqueueResponse,
    MessageItem,
    MessageRequest,
    MessagesResponse,
    SessionCreateResponse,
    SessionStatusResponse,
)
from entrypoints.api.dependencies.services import get_orchestration_service
from service_layer.application.agent_orchestration_service import AgentOrchestrationService


router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


def get_sqs_producer(request: Request) -> Optional[SQSProducerAdapter]:
    """Get SQS Producer from app state"""
    return getattr(request.app.state, "sqs_producer", None)


@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    status_code=201,
    summary="Create Agent Session",
    description="Create a new conversational agent session."
)
async def create_session(
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Create a new agent session"""
    session = await service.create_session()
    return SessionCreateResponse(
        session_id=session.id,
        status=session.status.value,
        created_at=session.created_at
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageEnqueueResponse,
    summary="Send Message",
    description="Send a message to a session. Returns immediately with processing status. Poll /status or /messages for agent response."
)
async def send_message(
    session_id: str,
    body: MessageRequest,
    service: AgentOrchestrationService = Depends(get_orchestration_service),
    sqs_producer: Optional[SQSProducerAdapter] = Depends(get_sqs_producer)
):
    """
    Send a message to an agent session.

    The message is saved and enqueued for async processing.
    Use GET /sessions/{session_id}/status to poll for completion.
    Use GET /sessions/{session_id}/messages to retrieve the agent response.
    """
    if sqs_producer is None:
        raise HTTPException(
            status_code=503,
            detail="Message processing is temporarily unavailable. SQS not configured."
        )

    try:
        result = await service.enqueue_message(
            session_id=session_id,
            content=body.content,
            sqs_producer=sqs_producer
        )
        return MessageEnqueueResponse(
            session_id=result.session_id,
            status=result.status,
            user_message_id=result.user_message_id
        )
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidSessionStateError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/sessions/{session_id}/messages",
    response_model=MessagesResponse,
    summary="Get Messages",
    description="Get conversation history for a session"
)
async def get_messages(
    session_id: str,
    limit: Optional[int] = Query(None, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Get conversation messages for a session"""
    try:
        messages = await service.get_messages(
            session_id=session_id,
            limit=limit,
            offset=offset
        )

        items = [
            MessageItem(
                id=msg.id,
                role=msg.role.value,
                content=msg.content,
                metadata=msg.metadata,
                created_at=msg.created_at
            )
            for msg in messages
        ]

        return MessagesResponse(
            session_id=session_id,
            messages=items,
            total_count=len(items),
            limit=limit,
            offset=offset
        )
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get(
    "/sessions/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Get Session Status",
    description="Get session status and metadata"
)
async def get_session_status(
    session_id: str,
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Get session status"""
    try:
        status = await service.get_session_status(session_id)
        return SessionStatusResponse(
            session_id=status.session_id,
            status=status.status,
            message_count=status.message_count,
            created_at=status.created_at,
            updated_at=status.updated_at,
            archived_at=status.archived_at
        )
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    summary="Delete Session",
    description="Permanently delete a session and all its messages"
)
async def delete_session(
    session_id: str,
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Delete a session and all its messages"""
    try:
        await service.delete_session(session_id)
        return None
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
