"""
Agent API Routes

REST API endpoints for agent session management.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from loguru import logger
from entrypoints.api.schemas.agent import (
    SessionCreateRequest,
    SessionCreateResponse,
    MessageRequest,
    MessageResponse,
    SessionStatusResponse,
    ObservationsResponse,
    ObservationItem,
    HITLRequest,
    HITLResponse,
    ObservationSummary,
)
from service_layer.application.agent_orchestration_service import AgentOrchestrationService
from service_layer.application.observation_service import ObservationService
from domain.exceptions import (
    AgentSessionNotFoundError,
    InvalidSessionStateError,
    LoopLimitExceededError,
)


router = APIRouter(prefix="/api/v1/agent", tags=["Agent"])


def get_orchestration_service(request: Request) -> AgentOrchestrationService:
    """Dependency for AgentOrchestrationService"""
    return AgentOrchestrationService(
        db_client=request.app.state.db_client,
        embedding_client=request.app.state.openai_client,
        max_loop_count=request.app.state.config.agent_max_loop_count
    )


def get_observation_service(request: Request) -> ObservationService:
    """Dependency for ObservationService"""
    return ObservationService(
        db_client=request.app.state.db_client
    )


@router.post(
    "/sessions",
    response_model=SessionCreateResponse,
    status_code=201,
    summary="Create Agent Session",
    description="Create a new agent session with a goal and optional context"
)
async def create_session(
    body: SessionCreateRequest,
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Create a new agent session"""
    try:
        session = await service.create_session(
            goal=body.goal,
            context=body.context
        )
        return SessionCreateResponse(
            session_id=session.id,
            status=session.status.value,
            goal=session.goal,
            created_at=session.created_at
        )
    except Exception as e:
        logger.error(f"Failed to create session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@router.post(
    "/sessions/{session_id}/messages",
    response_model=MessageResponse,
    summary="Send Message",
    description="Send a message to a session, starting or continuing agent processing"
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
            status=result["status"],
            loop_count=result["loop_count"],
            decision_type=result.get("decision_type"),
            hitl_request=result.get("hitl_request"),
            final_decision=result.get("final_decision")
        )
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidSessionStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except LoopLimitExceededError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to process message: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process message: {str(e)}")


@router.get(
    "/sessions/{session_id}/status",
    response_model=SessionStatusResponse,
    summary="Get Session Status",
    description="Poll session status and get current state"
)
async def get_session_status(
    session_id: str,
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Get session status (for polling)"""
    try:
        status = await service.get_session_status(session_id)
        return SessionStatusResponse(
            session_id=status["session_id"],
            status=status["status"],
            current_loop_count=status["current_loop_count"],
            max_loop_count=status["max_loop_count"],
            hitl_request=status.get("hitl_request"),
            final_decision=status.get("final_decision"),
            error_message=status.get("error_message"),
            created_at=status["created_at"],
            updated_at=status.get("updated_at"),
            observation_summary=ObservationSummary(**status["observation_summary"])
        )
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get session status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.get(
    "/sessions/{session_id}/observations",
    response_model=ObservationsResponse,
    summary="Get Observations",
    description="Get session observations with pagination"
)
async def get_observations(
    session_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    service: AgentOrchestrationService = Depends(get_orchestration_service),
    observation_service: ObservationService = Depends(get_observation_service)
):
    """Get observations for a session"""
    try:
        # Verify session exists
        await service.get_session(session_id)

        observations = await observation_service.get_observations(
            session_id=session_id,
            limit=limit,
            offset=offset
        )

        # Convert to response items
        items = [
            ObservationItem(
                id=obs.id,
                observation_type=obs.observation_type.value,
                content=obs.content,
                tool_name=obs.tool_name,
                is_error=obs.is_error,
                created_at=obs.created_at
            )
            for obs in observations
        ]

        return ObservationsResponse(
            session_id=session_id,
            observations=items,
            total_count=len(items),
            limit=limit,
            offset=offset
        )
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get observations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get observations: {str(e)}")


@router.post(
    "/sessions/{session_id}/hitl",
    response_model=HITLResponse,
    summary="Submit HITL Response",
    description="Submit human-in-the-loop response and resume processing"
)
async def submit_hitl_response(
    session_id: str,
    body: HITLRequest,
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Submit HITL response"""
    try:
        result = await service.submit_hitl_response(
            session_id=session_id,
            decision=body.decision
        )
        return HITLResponse(
            session_id=session_id,
            status=result["status"],
            message="HITL response received, resuming processing"
        )
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidSessionStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to submit HITL response: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to submit HITL: {str(e)}")


@router.delete(
    "/sessions/{session_id}",
    status_code=204,
    summary="Cancel Session",
    description="Cancel an active agent session"
)
async def cancel_session(
    session_id: str,
    service: AgentOrchestrationService = Depends(get_orchestration_service)
):
    """Cancel an active session"""
    try:
        await service.cancel_session(session_id)
        return None
    except AgentSessionNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidSessionStateError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to cancel session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to cancel session: {str(e)}")
