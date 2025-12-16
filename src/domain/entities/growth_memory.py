"""Growth Memory Domain Entity"""
from dataclasses import dataclass, fields as get_fields
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
from .base import BaseEntity
from domain.value_objects.agent_enums import GrowthMemoryType


@dataclass(eq=False, frozen=True)
class GrowthMemoryEntity(BaseEntity):
    """
    Growth memory domain entity

    Long-term memory storage with vector embeddings for RAG:
    - Session summaries, experiment results
    - Insights and patterns discovered
    - Vector embedding for semantic search
    """

    content: str
    memory_type: GrowthMemoryType
    embedding: List[float]
    created_at: datetime
    id: Optional[str] = None
    source_session_id: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        content: str,
        memory_type: GrowthMemoryType,
        embedding: List[float],
        source_session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "GrowthMemoryEntity":
        """
        Factory method for creating new GrowthMemoryEntity

        Args:
            content: Memory content/text
            memory_type: Type of memory
            embedding: Vector embedding (1536 dimensions for text-embedding-3-small)
            source_session_id: Optional source session ID
            tags: Optional tags for filtering
            metadata: Optional additional metadata

        Returns:
            New GrowthMemoryEntity instance
        """
        return cls(
            content=content,
            memory_type=memory_type,
            embedding=embedding,
            source_session_id=source_session_id,
            tags=tags or [],
            metadata=metadata,
            created_at=datetime.now(timezone.utc)
        )

    def __post_init__(self):
        self.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GrowthMemoryEntity":
        """Create entity from dictionary (MongoDB document)"""
        if "_id" in data:
            data = {**data}
            data["id"] = str(data.pop("_id"))

        # Validate required fields
        required_fields = ["content", "memory_type", "embedding", "created_at"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Field '{field}' is required")

        # Extract only defined fields
        known_fields = {f.name for f in get_fields(cls)}
        entity_data = {k: v for k, v in data.items() if k in known_fields}

        # Convert memory_type string to Enum
        if "memory_type" in entity_data and isinstance(entity_data["memory_type"], str):
            entity_data["memory_type"] = GrowthMemoryType(entity_data["memory_type"])

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
        if not isinstance(self.content, str) or not self.content.strip():
            raise ValueError("Field 'content' must be a non-empty string")

        if not isinstance(self.memory_type, GrowthMemoryType):
            raise ValueError("Field 'memory_type' must be a GrowthMemoryType enum")

        if not isinstance(self.embedding, list):
            raise ValueError("Field 'embedding' must be a list")

        if len(self.embedding) != 1536:
            raise ValueError("Field 'embedding' must have exactly 1536 dimensions")

        if not all(isinstance(x, (int, float)) for x in self.embedding):
            raise ValueError("Field 'embedding' must contain only numeric values")

        if not isinstance(self.created_at, datetime):
            raise ValueError("Field 'created_at' must be a datetime object")

        if self.tags is not None and not isinstance(self.tags, list):
            raise ValueError("Field 'tags' must be a list")

    def __eq__(self, other: object) -> bool:
        """Identity-based equality"""
        if not isinstance(other, GrowthMemoryEntity):
            return False
        if self.id is None or other.id is None:
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Identity-based hash"""
        if self.id is None:
            raise TypeError("Cannot hash GrowthMemoryEntity without id")
        return hash(self.id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dict with enum serialization"""
        result = super().to_dict()
        if isinstance(result.get("memory_type"), GrowthMemoryType):
            result["memory_type"] = result["memory_type"].value
        return result
