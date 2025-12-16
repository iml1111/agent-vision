"""Agent Session Domain Entity"""
from dataclasses import dataclass, fields as get_fields
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from .base import BaseEntity
from domain.value_objects.agent_enums import SessionStatus


@dataclass(eq=False, frozen=True)
class AgentSessionEntity(BaseEntity):
    """
    Agent session domain entity

    Represents a single agent session lifecycle with:
    - Goal and context for the agent
    - Status tracking (state machine)
    - Loop count management
    - HITL (Human-in-the-Loop) support
    - Final decision storage
    """

    goal: str
    context: Dict[str, Any]
    status: SessionStatus
    current_loop_count: int
    max_loop_count: int
    created_at: datetime
    id: Optional[str] = None
    updated_at: Optional[datetime] = None
    hitl_request: Optional[Dict[str, Any]] = None
    final_decision: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    @classmethod
    def create(
        cls,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        max_loop_count: int = 10
    ) -> "AgentSessionEntity":
        """
        Factory method for creating new AgentSessionEntity

        Args:
            goal: The goal/objective for the agent
            context: Additional context for the agent
            max_loop_count: Maximum number of loops allowed

        Returns:
            New AgentSessionEntity instance
        """
        return cls(
            goal=goal,
            context=context or {},
            status=SessionStatus.CREATED,
            current_loop_count=0,
            max_loop_count=max_loop_count,
            created_at=datetime.now(timezone.utc)
        )

    def __post_init__(self):
        self.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentSessionEntity":
        """Create entity from dictionary (MongoDB document)"""
        if "_id" in data:
            data = {**data}
            data["id"] = str(data.pop("_id"))

        # Validate required fields
        required_fields = ["goal", "context", "status", "current_loop_count", "max_loop_count", "created_at"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Field '{field}' is required")

        # Extract only defined fields
        known_fields = {f.name for f in get_fields(cls)}
        entity_data = {k: v for k, v in data.items() if k in known_fields}

        # Convert status string to Enum
        if "status" in entity_data and isinstance(entity_data["status"], str):
            entity_data["status"] = SessionStatus(entity_data["status"])

        # Convert timestamp string to UTC datetime
        for field in ["created_at", "updated_at"]:
            if field in entity_data and entity_data[field] is not None:
                if isinstance(entity_data[field], str):
                    entity_data[field] = datetime.fromisoformat(entity_data[field])
                elif isinstance(entity_data[field], datetime):
                    if entity_data[field].tzinfo is None:
                        entity_data[field] = entity_data[field].replace(tzinfo=timezone.utc)

        return cls(**entity_data)

    def validate(self) -> None:
        """Validate entity business rules"""
        if not isinstance(self.goal, str) or not self.goal.strip():
            raise ValueError("Field 'goal' must be a non-empty string")

        if not isinstance(self.context, dict):
            raise ValueError("Field 'context' must be a dict")

        if not isinstance(self.status, SessionStatus):
            raise ValueError("Field 'status' must be a SessionStatus enum")

        if not isinstance(self.current_loop_count, int) or self.current_loop_count < 0:
            raise ValueError("Field 'current_loop_count' must be a non-negative integer")

        if not isinstance(self.max_loop_count, int) or self.max_loop_count <= 0:
            raise ValueError("Field 'max_loop_count' must be a positive integer")

        if not isinstance(self.created_at, datetime):
            raise ValueError("Field 'created_at' must be a datetime object")

    def __eq__(self, other: object) -> bool:
        """Identity-based equality"""
        if not isinstance(other, AgentSessionEntity):
            return False
        if self.id is None or other.id is None:
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Identity-based hash"""
        if self.id is None:
            raise TypeError("Cannot hash AgentSessionEntity without id")
        return hash(self.id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dict with enum serialization"""
        result = super().to_dict()
        if isinstance(result.get("status"), SessionStatus):
            result["status"] = result["status"].value
        return result

    def is_terminal(self) -> bool:
        """Check if session is in a terminal state"""
        return self.status in [SessionStatus.COMPLETED, SessionStatus.FAILED, SessionStatus.CANCELLED]

    def can_continue(self) -> bool:
        """Check if session can continue processing"""
        return (
            self.status == SessionStatus.PROCESSING
            and self.current_loop_count < self.max_loop_count
        )
