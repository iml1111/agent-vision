"""Message Domain Entity"""
from dataclasses import dataclass, fields as get_fields
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from domain.value_objects.agent_enums import MessageRole

from .base import BaseEntity


@dataclass(eq=False, frozen=True)
class MessageEntity(BaseEntity):
    """
    Message domain entity

    Represents a single message in an agent conversation session.
    Replaces the previous Observation entity with a unified message model.

    Attributes:
        session_id: Parent session ID
        role: Message role (user, assistant, system)
        content: Message text content
        metadata: Optional metadata (tool_calls, errors, rag_results, etc.)
        created_at: Message creation timestamp
        id: MongoDB document ID
    """

    session_id: str
    role: MessageRole
    content: str
    created_at: datetime
    id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        session_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "MessageEntity":
        """
        Factory method for creating new MessageEntity

        Args:
            session_id: Parent session ID
            role: Message role
            content: Message text content
            metadata: Optional metadata

        Returns:
            New MessageEntity instance
        """
        return cls(
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata,
            created_at=datetime.now(timezone.utc)
        )

    def __post_init__(self):
        self.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MessageEntity":
        """Create entity from dictionary (MongoDB document)"""
        if "_id" in data:
            data = {**data}
            data["id"] = str(data.pop("_id"))

        # Validate required fields
        required_fields = ["session_id", "role", "content", "created_at"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Field '{field}' is required")

        # Extract only defined fields
        known_fields = {f.name for f in get_fields(cls)}
        entity_data = {k: v for k, v in data.items() if k in known_fields}

        # Convert role string to Enum
        if "role" in entity_data and isinstance(entity_data["role"], str):
            entity_data["role"] = MessageRole(entity_data["role"])

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

        if not isinstance(self.role, MessageRole):
            raise ValueError("Field 'role' must be a MessageRole enum")

        if not isinstance(self.content, str):
            raise ValueError("Field 'content' must be a string")

        if not isinstance(self.created_at, datetime):
            raise ValueError("Field 'created_at' must be a datetime object")

        if self.metadata is not None and not isinstance(self.metadata, dict):
            raise ValueError("Field 'metadata' must be a dict or None")

    def __eq__(self, other: object) -> bool:
        """Identity-based equality"""
        if not isinstance(other, MessageEntity):
            return False
        if self.id is None or other.id is None:
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Identity-based hash"""
        if self.id is None:
            raise TypeError("Cannot hash MessageEntity without id")
        return hash(self.id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dict with enum serialization"""
        result = super().to_dict()
        if isinstance(result.get("role"), MessageRole):
            result["role"] = result["role"].value
        return result
