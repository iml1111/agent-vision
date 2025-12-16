"""
Agent API Schemas

Request/Response schemas for agent endpoints.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================


class SessionCreateRequest(BaseModel):
    """Request schema for creating a new agent session"""
    goal: str = Field(..., min_length=1, max_length=2000, description="The goal/objective for the agent")
    context: Optional[Dict[str, Any]] = Field(None, description="Optional additional context")

    model_config = {"json_schema_extra": {
        "example": {
            "goal": "Analyze user retention for the past 30 days and suggest improvements",
            "context": {"product_area": "onboarding", "target_metric": "d7_retention"}
        }
    }}


class MessageRequest(BaseModel):
    """Request schema for sending a message to a session"""
    content: Optional[str] = Field(None, max_length=5000, description="Optional message content")

    model_config = {"json_schema_extra": {
        "example": {
            "content": "Focus on mobile users specifically"
        }
    }}


class HITLRequest(BaseModel):
    """Request schema for submitting HITL response"""
    decision: Dict[str, Any] = Field(..., description="HITL decision/response")

    model_config = {"json_schema_extra": {
        "example": {
            "decision": {
                "choice": "option_a",
                "reason": "We want to focus on new user onboarding first",
                "additional_context": "Budget is limited for Q1"
            }
        }
    }}


# =============================================================================
# Response Schemas
# =============================================================================


class SessionCreateResponse(BaseModel):
    """Response schema for session creation"""
    session_id: str
    status: str
    goal: str
    created_at: datetime

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "status": "created",
            "goal": "Analyze user retention for the past 30 days",
            "created_at": "2025-01-15T10:30:00Z"
        }
    }}


class MessageResponse(BaseModel):
    """Response schema for message processing"""
    session_id: str
    status: str
    loop_count: int
    decision_type: Optional[str] = None
    hitl_request: Optional[Dict[str, Any]] = None
    final_decision: Optional[Dict[str, Any]] = None

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "status": "processing",
            "loop_count": 1,
            "decision_type": "continue"
        }
    }}


class ObservationSummary(BaseModel):
    """Summary of session observations"""
    total_observations: int
    error_count: int
    tool_call_count: int
    rag_retrieval_count: int
    tools_used: List[str]


class SessionStatusResponse(BaseModel):
    """Response schema for session status"""
    session_id: str
    status: str
    current_loop_count: int
    max_loop_count: int
    hitl_request: Optional[Dict[str, Any]] = None
    final_decision: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    observation_summary: ObservationSummary

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "status": "completed",
            "current_loop_count": 3,
            "max_loop_count": 10,
            "final_decision": {
                "recommendation": "Implement onboarding tutorial",
                "expected_impact": "15% improvement in D7 retention"
            },
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": "2025-01-15T10:35:00Z",
            "observation_summary": {
                "total_observations": 12,
                "error_count": 0,
                "tool_call_count": 8,
                "rag_retrieval_count": 2,
                "tools_used": ["funnel_analysis", "search_growth_memory"]
            }
        }
    }}


class ObservationItem(BaseModel):
    """Individual observation item"""
    id: str
    observation_type: str
    content: Dict[str, Any]
    tool_name: Optional[str] = None
    is_error: bool
    created_at: datetime


class ObservationsResponse(BaseModel):
    """Response schema for observations list"""
    session_id: str
    observations: List[ObservationItem]
    total_count: int
    limit: int
    offset: int


class HITLResponse(BaseModel):
    """Response schema for HITL submission"""
    session_id: str
    status: str
    message: str

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "status": "processing",
            "message": "HITL response received, resuming processing"
        }
    }}


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    session_id: Optional[str] = None
