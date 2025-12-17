"""GrowthMemory Domain Entity"""
from dataclasses import dataclass, fields as get_fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseEntity


@dataclass(eq=False, frozen=True)
class GrowthMemoryEntity(BaseEntity):
    """
    GrowthMemory domain entity

    Represents a summarized session insight stored as long-term memory.
    Contains 6 structured summary units and a vector embedding for semantic search.

    Attributes:
        session_id: Reference to original AgentSession
        created_at: Memory creation timestamp
        id: MongoDB document ID

        # 6 Summary Units
        problem_snapshot: Problem context and background
        bottleneck_evidence: Identified bottlenecks with evidence
        hypotheses: Generated hypotheses list
        experiment_cards: Structured experiment designs
        outcome: Results and conclusions
        learnings_next_actions: Key takeaways and recommended next steps

        # Vector Search
        content_vector: 1536-dim embedding for Atlas Vector Search
        vector_text: Source text used for embedding generation

        # Metadata
        message_count: Original session message count
        session_created_at: Original session creation time
        session_archived_at: Session archive timestamp
    """

    # Core identifiers
    session_id: str
    created_at: datetime
    id: Optional[str] = None

    # 6 Summary Units (all Optional - may not apply to every session)
    problem_snapshot: Optional[str] = None
    bottleneck_evidence: Optional[str] = None
    hypotheses: Optional[List[str]] = None
    experiment_cards: Optional[List[Dict[str, Any]]] = None
    outcome: Optional[str] = None
    learnings_next_actions: Optional[str] = None

    # Vector Search
    content_vector: Optional[List[float]] = None
    vector_text: Optional[str] = None

    # Metadata
    message_count: int = 0
    session_created_at: Optional[datetime] = None
    session_archived_at: Optional[datetime] = None

    @classmethod
    def create(
        cls,
        session_id: str,
        problem_snapshot: Optional[str] = None,
        bottleneck_evidence: Optional[str] = None,
        hypotheses: Optional[List[str]] = None,
        experiment_cards: Optional[List[Dict[str, Any]]] = None,
        outcome: Optional[str] = None,
        learnings_next_actions: Optional[str] = None,
        content_vector: Optional[List[float]] = None,
        vector_text: Optional[str] = None,
        message_count: int = 0,
        session_created_at: Optional[datetime] = None,
        session_archived_at: Optional[datetime] = None
    ) -> "GrowthMemoryEntity":
        """
        Factory method for creating new GrowthMemoryEntity

        Args:
            session_id: Reference to original AgentSession
            problem_snapshot: Problem context and background
            bottleneck_evidence: Identified bottlenecks with evidence
            hypotheses: Generated hypotheses list
            experiment_cards: Structured experiment designs
            outcome: Results and conclusions
            learnings_next_actions: Key takeaways and next steps
            content_vector: Embedding vector for search
            vector_text: Source text for embedding
            message_count: Original session message count
            session_created_at: Original session creation time
            session_archived_at: Session archive timestamp

        Returns:
            New GrowthMemoryEntity instance
        """
        return cls(
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            problem_snapshot=problem_snapshot,
            bottleneck_evidence=bottleneck_evidence,
            hypotheses=hypotheses,
            experiment_cards=experiment_cards,
            outcome=outcome,
            learnings_next_actions=learnings_next_actions,
            content_vector=content_vector,
            vector_text=vector_text,
            message_count=message_count,
            session_created_at=session_created_at,
            session_archived_at=session_archived_at
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
        required_fields = ["session_id", "created_at"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Field '{field}' is required")

        # Extract only defined fields
        known_fields = {f.name for f in get_fields(cls)}
        entity_data = {k: v for k, v in data.items() if k in known_fields}

        # Convert timestamp strings to UTC datetime
        datetime_fields = ["created_at", "session_created_at", "session_archived_at"]
        for field in datetime_fields:
            if field in entity_data and entity_data[field] is not None:
                if isinstance(entity_data[field], str):
                    entity_data[field] = datetime.fromisoformat(entity_data[field])
                elif isinstance(entity_data[field], datetime):
                    if entity_data[field].tzinfo is None:
                        entity_data[field] = entity_data[field].replace(tzinfo=timezone.utc)

        return cls(**entity_data)

    def validate(self) -> None:
        """Validate entity business rules"""
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("Field 'session_id' must be a non-empty string")

        if not isinstance(self.created_at, datetime):
            raise ValueError("Field 'created_at' must be a datetime object")

        if self.content_vector is not None:
            if not isinstance(self.content_vector, list):
                raise ValueError("Field 'content_vector' must be a list or None")

        if self.hypotheses is not None:
            if not isinstance(self.hypotheses, list):
                raise ValueError("Field 'hypotheses' must be a list or None")

        if self.experiment_cards is not None:
            if not isinstance(self.experiment_cards, list):
                raise ValueError("Field 'experiment_cards' must be a list or None")

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
