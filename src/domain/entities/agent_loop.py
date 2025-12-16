"""Agent Loop Domain Entity"""
from dataclasses import dataclass, fields as get_fields
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from .base import BaseEntity
from domain.value_objects.agent_enums import LoopPhase


@dataclass(eq=False, frozen=True)
class AgentLoopEntity(BaseEntity):
    """
    Agent loop domain entity

    Represents a single iteration of the Plan→Act→Observe→Critique→Decide loop:
    - Tracks phase progression
    - Stores output from each phase
    - Links to parent session
    """

    session_id: str
    iteration: int
    phase: LoopPhase
    created_at: datetime
    id: Optional[str] = None
    updated_at: Optional[datetime] = None
    plan_output: Optional[Dict[str, Any]] = None
    act_output: Optional[Dict[str, Any]] = None
    observe_output: Optional[Dict[str, Any]] = None
    critique_output: Optional[Dict[str, Any]] = None
    decide_output: Optional[Dict[str, Any]] = None

    @classmethod
    def create(
        cls,
        session_id: str,
        iteration: int
    ) -> "AgentLoopEntity":
        """
        Factory method for creating new AgentLoopEntity

        Args:
            session_id: Parent session ID
            iteration: Loop iteration number (0-indexed)

        Returns:
            New AgentLoopEntity instance
        """
        return cls(
            session_id=session_id,
            iteration=iteration,
            phase=LoopPhase.PLAN,
            created_at=datetime.now(timezone.utc)
        )

    def __post_init__(self):
        self.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentLoopEntity":
        """Create entity from dictionary (MongoDB document)"""
        if "_id" in data:
            data = {**data}
            data["id"] = str(data.pop("_id"))

        # Validate required fields
        required_fields = ["session_id", "iteration", "phase", "created_at"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Field '{field}' is required")

        # Extract only defined fields
        known_fields = {f.name for f in get_fields(cls)}
        entity_data = {k: v for k, v in data.items() if k in known_fields}

        # Convert phase string to Enum
        if "phase" in entity_data and isinstance(entity_data["phase"], str):
            entity_data["phase"] = LoopPhase(entity_data["phase"])

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
        if not isinstance(self.session_id, str) or not self.session_id.strip():
            raise ValueError("Field 'session_id' must be a non-empty string")

        if not isinstance(self.iteration, int) or self.iteration < 0:
            raise ValueError("Field 'iteration' must be a non-negative integer")

        if not isinstance(self.phase, LoopPhase):
            raise ValueError("Field 'phase' must be a LoopPhase enum")

        if not isinstance(self.created_at, datetime):
            raise ValueError("Field 'created_at' must be a datetime object")

    def __eq__(self, other: object) -> bool:
        """Identity-based equality"""
        if not isinstance(other, AgentLoopEntity):
            return False
        if self.id is None or other.id is None:
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Identity-based hash"""
        if self.id is None:
            raise TypeError("Cannot hash AgentLoopEntity without id")
        return hash(self.id)

    def to_dict(self) -> Dict[str, Any]:
        """Convert entity to dict with enum serialization"""
        result = super().to_dict()
        if isinstance(result.get("phase"), LoopPhase):
            result["phase"] = result["phase"].value
        return result

    def get_phase_output(self, phase: LoopPhase) -> Optional[Dict[str, Any]]:
        """Get output for a specific phase"""
        phase_outputs = {
            LoopPhase.PLAN: self.plan_output,
            LoopPhase.ACT: self.act_output,
            LoopPhase.OBSERVE: self.observe_output,
            LoopPhase.CRITIQUE: self.critique_output,
            LoopPhase.DECIDE: self.decide_output,
        }
        return phase_outputs.get(phase)
