"""SubAgentTrace Domain Entity"""
from dataclasses import dataclass, fields as get_fields
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .base import BaseEntity


@dataclass(eq=False, frozen=True)
class SubAgentTraceEntity(BaseEntity):
    """
    SubAgentTrace domain entity

    Represents a trace record for sub-agent execution.
    Stores all internal events for debugging and analysis purposes.

    Attributes:
        session_id: Parent AgentSession ID
        parent_message_id: ID of the Supervisor TOOL_USE message that triggered this execution
        agent_name: Sub-agent identifier (e.g., "slack", "product", "data", "memory")
        task: Task description delegated by Supervisor
        created_at: Trace creation timestamp
        id: MongoDB document ID

        events: List of internal events (TEXT, TOOL_USE, etc.)
        result: Final response returned to Supervisor
        started_at: Execution start timestamp
        completed_at: Execution end timestamp
        duration_ms: Execution duration in milliseconds
        model: Claude model used
        error: Error message if execution failed
    """

    # Core identifiers (required)
    session_id: str
    agent_name: str
    task: str
    created_at: datetime
    id: Optional[str] = None
    parent_message_id: Optional[str] = None  # Set later via update_parent_message_id

    # Execution details (optional)
    events: Optional[List[Dict[str, Any]]] = None
    result: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    model: Optional[str] = None
    error: Optional[str] = None

    @classmethod
    def create(
        cls,
        session_id: str,
        agent_name: str,
        task: str,
        parent_message_id: Optional[str] = None,
        events: Optional[List[Dict[str, Any]]] = None,
        result: Optional[str] = None,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        model: Optional[str] = None,
        error: Optional[str] = None
    ) -> "SubAgentTraceEntity":
        """
        Factory method for creating new SubAgentTraceEntity

        Args:
            session_id: Parent AgentSession ID
            agent_name: Sub-agent identifier
            task: Task description
            parent_message_id: ID of triggering Supervisor TOOL_USE message (set later)
            events: List of internal events
            result: Final response
            started_at: Execution start time
            completed_at: Execution end time
            duration_ms: Execution duration
            model: Claude model used
            error: Error message if failed

        Returns:
            New SubAgentTraceEntity instance
        """
        return cls(
            session_id=session_id,
            agent_name=agent_name,
            task=task,
            created_at=datetime.now(timezone.utc),
            parent_message_id=parent_message_id,
            events=events,
            result=result,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            model=model,
            error=error
        )

    def __post_init__(self):
        self.validate()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SubAgentTraceEntity":
        """Create entity from dictionary (MongoDB document)"""
        if "_id" in data:
            data = {**data}
            data["id"] = str(data.pop("_id"))

        # Validate required fields (parent_message_id is optional - set later via update)
        required_fields = ["session_id", "agent_name", "task", "created_at"]
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Field '{field}' is required")

        # Extract only defined fields
        known_fields = {f.name for f in get_fields(cls)}
        entity_data = {k: v for k, v in data.items() if k in known_fields}

        # Convert timestamp strings to UTC datetime
        datetime_fields = ["created_at", "started_at", "completed_at"]
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

        # parent_message_id is optional (set later via update_parent_message_id)
        if self.parent_message_id is not None:
            if not isinstance(self.parent_message_id, str) or not self.parent_message_id.strip():
                raise ValueError("Field 'parent_message_id' must be a non-empty string or None")

        if not isinstance(self.agent_name, str) or not self.agent_name.strip():
            raise ValueError("Field 'agent_name' must be a non-empty string")

        if not isinstance(self.task, str):
            raise ValueError("Field 'task' must be a string")

        if not isinstance(self.created_at, datetime):
            raise ValueError("Field 'created_at' must be a datetime object")

        if self.events is not None:
            if not isinstance(self.events, list):
                raise ValueError("Field 'events' must be a list or None")

        if self.duration_ms is not None:
            if not isinstance(self.duration_ms, int) or self.duration_ms < 0:
                raise ValueError("Field 'duration_ms' must be a non-negative integer or None")

    def __eq__(self, other: object) -> bool:
        """Identity-based equality"""
        if not isinstance(other, SubAgentTraceEntity):
            return False
        if self.id is None or other.id is None:
            return False
        return self.id == other.id

    def __hash__(self) -> int:
        """Identity-based hash"""
        if self.id is None:
            raise TypeError("Cannot hash SubAgentTraceEntity without id")
        return hash(self.id)
