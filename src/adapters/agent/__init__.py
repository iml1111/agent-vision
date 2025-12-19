"""Agent Adapter - Claude SDK Integration"""
from .options import create_growth_agent_options
from .client import GrowthAgentClient

# Re-export from submodules for convenience
from .tools import GROWTH_TOOL_NAMES

# Re-export domain types for convenience (canonical source: domain.value_objects)
from domain.value_objects import (
    AgentMessageType,
    ToolCallVO,
    AgentStreamEvent,
)

__all__ = [
    # Core agent components
    "create_growth_agent_options",
    "GrowthAgentClient",
    # Tools
    "GROWTH_TOOL_NAMES",
    # Domain types (re-exported for convenience)
    "AgentMessageType",
    "ToolCallVO",
    "AgentStreamEvent",
]
