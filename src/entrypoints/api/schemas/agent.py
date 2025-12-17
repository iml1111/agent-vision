"""
Agent API Schemas

Request/Response schemas for conversational agent endpoints.
"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


# =============================================================================
# Request Schemas
# =============================================================================


class SessionCreateRequest(BaseModel):
    """Request schema for creating a new agent session (empty body allowed)"""

    model_config = {"json_schema_extra": {
        "example": {}
    }}


class MessageRequest(BaseModel):
    """Request schema for sending a message to a session"""
    content: str = Field(..., min_length=1, max_length=10000, description="Message content")

    model_config = {"json_schema_extra": {
        "example": {
            "content": "Focus on mobile users specifically"
        }
    }}


class ArchiveRequest(BaseModel):
    """Request schema for archiving a session"""
    reason: Optional[str] = Field(None, max_length=500, description="Optional archive reason")

    model_config = {"json_schema_extra": {
        "example": {
            "reason": "Analysis complete, moving to implementation phase"
        }
    }}


# =============================================================================
# Response Schemas
# =============================================================================


class SessionCreateResponse(BaseModel):
    """Response schema for session creation"""
    session_id: str
    status: str
    goal: Optional[str] = None
    created_at: datetime

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "status": "active",
            "goal": None,
            "created_at": "2025-01-15T10:30:00Z"
        }
    }}


class MessageResponse(BaseModel):
    """Response schema for message processing (agent response)"""
    session_id: str
    role: str
    content: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    created_at: datetime

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "role": "assistant",
            "content": "I've analyzed the retention data. Here are my findings...",
            "tool_calls": [{"name": "funnel_analysis", "result": {"conversion_rate": 0.45}}],
            "created_at": "2025-01-15T10:30:15Z"
        }
    }}


class SessionStatusResponse(BaseModel):
    """Response schema for session status"""
    session_id: str
    goal: Optional[str] = None
    status: str
    message_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    archive_reason: Optional[str] = None

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "goal": "Analyze user retention for mobile users",
            "status": "active",
            "message_count": 5,
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": "2025-01-15T10:35:00Z",
            "archived_at": None,
            "archive_reason": None
        }
    }}


class MessageItem(BaseModel):
    """Individual message item"""
    id: str
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime


class MessagesResponse(BaseModel):
    """Response schema for messages list"""
    session_id: str
    messages: List[MessageItem]
    total_count: int
    limit: Optional[int] = None
    offset: int

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "messages": [
                {
                    "id": "507f1f77bcf86cd799439012",
                    "role": "user",
                    "content": "Analyze mobile retention",
                    "metadata": None,
                    "created_at": "2025-01-15T10:30:00Z"
                },
                {
                    "id": "507f1f77bcf86cd799439013",
                    "role": "assistant",
                    "content": "I've analyzed the mobile retention data...",
                    "metadata": {"tool_calls": []},
                    "created_at": "2025-01-15T10:30:15Z"
                }
            ],
            "total_count": 2,
            "limit": 50,
            "offset": 0
        }
    }}


class ArchiveResponse(BaseModel):
    """Response schema for session archive"""
    session_id: str
    status: str
    archived_at: datetime
    message: str

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "status": "archived",
            "archived_at": "2025-01-15T12:00:00Z",
            "message": "Session archived successfully"
        }
    }}
