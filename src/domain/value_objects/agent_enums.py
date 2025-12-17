"""Agent Value Objects - Enums"""
from enum import Enum


class SessionStatus(str, Enum):
    """Agent session status enumeration (conversational model)"""
    ACTIVE = "active"       # 대화 진행 중
    PAUSED = "paused"       # 일시 중지
    ARCHIVED = "archived"   # 보관됨 (다시 활성화 가능)


class MessageRole(str, Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class GrowthMemoryType(str, Enum):
    """Growth memory type enumeration"""
    SESSION_SUMMARY = "session_summary"
    EXPERIMENT_RESULT = "experiment_result"
    INSIGHT = "insight"
    PATTERN = "pattern"
