"""Agent Value Objects - Enums"""
from enum import Enum


class SessionStatus(str, Enum):
    """Agent session status enumeration"""
    CREATED = "created"
    PROCESSING = "processing"
    WAITING_HITL = "waiting_hitl"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class LoopPhase(str, Enum):
    """Agent loop phase enumeration (Plan→Act→Observe→Critique→Decide)"""
    PLAN = "plan"
    ACT = "act"
    OBSERVE = "observe"
    CRITIQUE = "critique"
    DECIDE = "decide"


class ObservationType(str, Enum):
    """Observation type enumeration"""
    TOOL_RESULT = "tool_result"
    CONTEXT = "context"
    ERROR = "error"
    HITL_RESPONSE = "hitl_response"
    RAG_RETRIEVAL = "rag_retrieval"


class DecisionType(str, Enum):
    """Decision type enumeration"""
    EXPERIMENT = "experiment"
    HITL_QUESTION = "hitl_question"
    INSTRUMENTATION_TODO = "instrumentation_todo"
    CONTINUE = "continue"


class GrowthMemoryType(str, Enum):
    """Growth memory type enumeration"""
    SESSION_SUMMARY = "session_summary"
    EXPERIMENT_RESULT = "experiment_result"
    INSIGHT = "insight"
    PATTERN = "pattern"
