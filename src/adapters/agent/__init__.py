"""Agent Adapter - Claude SDK Integration"""
from .options import create_growth_agent_options
from .client import GrowthAgentClient

# Re-export from submodules for convenience
from .tools import GROWTH_TOOLS, GROWTH_TOOL_NAMES
from .hooks import (
    validate_slack_allowlist,
    validate_notion_allowlist,
    log_tool_call,
    capture_observation,
    audit_log,
)

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
    "GROWTH_TOOLS",
    "GROWTH_TOOL_NAMES",
    # Hooks
    "validate_slack_allowlist",
    "validate_notion_allowlist",
    "log_tool_call",
    "capture_observation",
    "audit_log",
    # Domain types (re-exported for convenience)
    "AgentMessageType",
    "ToolCallVO",
    "AgentStreamEvent",
]
