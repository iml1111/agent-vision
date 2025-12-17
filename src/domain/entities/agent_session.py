"""Agent Session Domain Entity"""
from dataclasses import dataclass, fields as get_fields
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from domain.value_objects.agent_enums import SessionStatus

from .base import BaseEntity


@dataclass(eq=False, frozen=True)
class AgentSessionEntity(BaseEntity):
    """
    Agent session domain entity (conversational model)

    Represents a continuous conversation session with:
    - Goal set from first message (optional until first message)
    - Simple status tracking (ACTIVE, PAUSED, ARCHIVED)
    - No loop limits or workflow constraints
    """

    status: SessionStatus
    created_at: datetime
    id: Optional[str] = None
    goal: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None
    archive_reason: Optional[str] = None

    @classmethod
    def create(cls) -> "AgentSessionEntity":
        """
        Factory method for creating new AgentSessionEntity

        Goal will be set from the first message.

        Returns:
            New AgentSessionEntity instance
        """
        return cls(
            status=SessionStatus.ACTIVE,
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
        required_fields = ["status", "created_at"]
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
        for field in ["created_at", "updated_at", "archived_at"]:
            if field in entity_data and entity_data[field] is not None:
                if isinstance(entity_data[field], str):
                    entity_data[field] = datetime.fromisoformat(entity_data[field])
                elif isinstance(entity_data[field], datetime):
                    if entity_data[field].tzinfo is None:
                        entity_data[field] = entity_data[field].replace(tzinfo=timezone.utc)

        return cls(**entity_data)

    def validate(self) -> None:
        """Validate entity business rules"""
        # goal is optional (set from first message)
        if self.goal is not None and not isinstance(self.goal, str):
            raise ValueError("Field 'goal' must be a string if provided")

        # context is optional
        if self.context is not None and not isinstance(self.context, dict):
            raise ValueError("Field 'context' must be a dict if provided")

        if not isinstance(self.status, SessionStatus):
            raise ValueError("Field 'status' must be a SessionStatus enum")

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

    def is_active(self) -> bool:
        """Check if session is active for conversation"""
        return self.status == SessionStatus.ACTIVE

    def is_archived(self) -> bool:
        """Check if session is archived"""
        return self.status == SessionStatus.ARCHIVED

    def has_goal(self) -> bool:
        """Check if session has a goal set (first message received)"""
        return self.goal is not None and len(self.goal.strip()) > 0
