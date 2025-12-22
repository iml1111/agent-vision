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




# =============================================================================
# Response Schemas
# =============================================================================


class SessionCreateResponse(BaseModel):
    """Response schema for session creation"""
    session_id: str
    status: str
    created_at: datetime

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "status": "active",
            "created_at": "2025-01-15T10:30:00Z"
        }
    }}


class MessageEnqueueResponse(BaseModel):
    """Response schema when message is enqueued for async processing"""
    session_id: str
    status: str  # "processing"
    user_message_id: str

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "status": "processing",
            "user_message_id": "507f1f77bcf86cd799439012"
        }
    }}


class MessageResponse(BaseModel):
    """Response schema for message with agent response (used for polling results)"""
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
    status: str
    message_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None

    model_config = {"json_schema_extra": {
        "example": {
            "session_id": "507f1f77bcf86cd799439011",
            "status": "active",
            "message_count": 5,
            "created_at": "2025-01-15T10:30:00Z",
            "updated_at": "2025-01-15T10:35:00Z",
            "archived_at": None
        }
    }}


class TraceEventItem(BaseModel):
    """Sub-agent trace event (tool call)"""
    type: str  # "text" | "tool_use"
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None


class MessageItem(BaseModel):
    """Individual message item"""
    id: str
    role: str
    content: str
    metadata: Optional[Dict[str, Any]] = None
    traces: Optional[List[TraceEventItem]] = None  # Sub-agent tool calls
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


