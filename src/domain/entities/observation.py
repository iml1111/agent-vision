"""Observation Domain Entity"""
from dataclasses import dataclass, fields as get_fields
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from .base import BaseEntity
from domain.value_objects.agent_enums import ObservationType


@dataclass(eq=False, frozen=True)
class ObservationEntity(BaseEntity):
    """
    Observation domain entity

    Represents ephemeral observations during agent execution:
    - Tool results, context updates, errors
    - HITL responses, RAG retrieval results
    - Short-term memory within a session
    """

    session_id: str
    observation_type: ObservationType
    content: Dict[str, Any]
    created_at: datetime
    id: Optional[str] = None
    loop_id: Optional[str] = None
    tool_name: Optional[str] = None
    is_error: bool = False

    @classmethod
    def create(
        cls,
        session_id: str,
        observation_type: ObservationType,
        content: Dict[str, Any],
        loop_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        is_error: bool = False
    ) -> "ObservationEntity":
        """
        Factory method for creating new ObservationEntity

        Args:
            session_id: Parent session ID
            observation_type: Type of observation
            content: Observation content/data
            loop_id: Optional parent loop ID
            tool_name: Optional tool that generated this observation
            is_error: Whether this is an error observation

        Returns:
            New ObservationEntity instance
        """
        return cls(
            session_id=session_id,
            observation_type=observation_type,
            content=content,
            loop_id=loop_id,
            tool_name=tool_name,
            is_error=is_error,
            created_at=datetime.now(timezone.utc)
        )

    def __post_init__(self):
        self.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ObservationEntity":
        """Create entity from dictionary (MongoDB document)"""
        if "_id" in data:
            data = {**data}
            data["id"] = str(data.pop("_id"))

        # Validate required fields
        required_fields = ["session_id", "observation_type", "content", "created_at"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Field '{field}' is required")

        # Extract only defined fields
        known_fields = {f.name for f in get_fields(cls)}
        entity_data = {k: v for k, v in data.items() if k in known_fields}

        # Convert observation_type string to Enum
        if "observation_type" in entity_data and isinstance(entity_data["observation_type"], str):
            entity_data["observation_type"] = ObservationType(entity_data["observation_type"])

        # Convert timestamp string to UTC datetime
        if "created_at" in entity_data and entity_data["created_at"] is not None:
            if isinstance(entity_data["created_at"], str):
                entity_data["created_at"] = datetime.fromisoformat(entity_data["created_at"])
            elif isinstance(entity_data["created_at"], datetime):
                if entity_data["created_at"].tzinfo is None:
                    entity_data["created_at"] = entity_data["created_at"].replace(tzinfo=timezone.utc)

        return cls(**entity_data)

    def validate(self) -> None:
        """Validate entity business rules"""
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("Field 'session_id' must be a non-empty string")

        if not isinstance(self.observation_type, ObservationType):
            raise ValueError("Field 'observation_type' must be an ObservationType enum")

        if not isinstance(self.content, dict):
            raise ValueError("Field 'content' must be a dict")

        if not isinstance(self.created_at, datetime):
            raise ValueError("Field 'created_at' must be a datetime object")

        if not isinstance(self.is_error, bool):
            raise ValueError("Field 'is_error' must be a boolean")

    def __eq__(self, other: object) -> bool:
        """Identity-based equality"""
        if not isinstance(other, ObservationEntity):
            return False
        if self.id is None or other.id is None:
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Identity-based hash"""
        if self.id is None:
            raise TypeError("Cannot hash ObservationEntity without id")
        return hash(self.id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dict with enum serialization"""
        result = super().to_dict()
        if isinstance(result.get("observation_type"), ObservationType):
            result["observation_type"] = result["observation_type"].value
        return result
