"""Agent Value Objects - Enums"""
from enum import Enum


class SessionStatus(str, Enum):
    """Agent session status enumeration (conversational model)"""
    ACTIVE = "active"           # 대화 진행 중
    PROCESSING = "processing"   # 에이전트 응답 생성 중 (사용자 입력 불가)
    ARCHIVED = "archived"       # 보관됨 (다시 활성화 가능)


class MessageRole(str, Enum):
    """Message role enumeration"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    # Sub-agent roles (for flattened sub-agent events)
    SUBAGENT_SLACK = "subagent_slack"
    SUBAGENT_PRODUCT = "subagent_product"
    SUBAGENT_DATA = "subagent_data"
    SUBAGENT_MEMORY = "subagent_memory"
