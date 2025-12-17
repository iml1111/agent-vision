"""
Agent API Routes

REST API endpoints for conversational agent session management.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
)
from entrypoints.api.schemas.agent import (
    ArchiveRequest,
    ArchiveResponse,
    MessageItem,
    MessageRequest,
    MessageResponse,
    MessagesResponse,
    SessionCreateResponse,
    SessionStatusResponse,
)
from entrypoints.api.dependencies.services import get_orchestration_service
from service_layer.application.agent_orchestration_service import AgentOrchestrationService


router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    status_code=201,
    summary="Create Agent Session",
    description="Create a new conversational agent session. Goal is set from the first message."
)
async def create_session(
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Create a new agent session (goal will be set from first message)"""
    session = await service.create_session()
    return SessionCreateResponse(
        session_id=session.id,
        status=session.status.value,
        goal=session.goal,
        created_at=session.created_at
    )


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    summary="Send Message",
    description="Send a message to a session and receive agent response"
)
async def send_message(
    session_id: str,
    body: MessageRequest,
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Send a message to an agent session"""
    try:
        result = await service.process_message(
            session_id=session_id,
            content=body.content
        )
        return MessageResponse(
            session_id=result["session_id"],
            role=result["role"],
            content=result["content"],
            tool_calls=result.get("tool_calls"),
            created_at=datetime.fromisoformat(result["created_at"])
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
            session_id=status["session_id"],
            goal=status["goal"],
            status=status["status"],
            message_count=status["message_count"],
            created_at=datetime.fromisoformat(status["created_at"]),
            updated_at=datetime.fromisoformat(status["updated_at"]) if status.get("updated_at") else None,
            archived_at=datetime.fromisoformat(status["archived_at"]) if status.get("archived_at") else None,
            archive_reason=status.get("archive_reason")
        )
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post(
    "/sessions/{session_id}/archive",
    response_model=ArchiveResponse,
    summary="Archive Session",
    description="Archive a session for later reference"
)
async def archive_session(
    session_id: str,
    body: Optional[ArchiveRequest] = None,
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Archive a session"""
    try:
        reason = body.reason if body else None
        await service.archive_session(session_id=session_id, reason=reason)

        return ArchiveResponse(
            session_id=session_id,
            status="archived",
            archived_at=datetime.now(timezone.utc),
            message="Session archived successfully"
        )
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidSessionStateError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
