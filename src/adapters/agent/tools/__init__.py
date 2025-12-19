"""Agent Tools Factory Functions"""
from typing import List

from .eventlog_tool import create_eventlog_tools
from .growth_memory_tool import create_growth_memory_tools
from .notion_tool import create_notion_tools
from .slack_tool import create_slack_tools

# Tool names for allowed_tools configuration
GROWTH_TOOL_NAMES: List[str] = [
    "mcp__growth-tools__run_eventlog_aggregation",
    "mcp__growth-tools__list_slack_channels",
    "mcp__growth-tools__get_slack_messages",
    "mcp__growth-tools__list_notion_pages",
    "mcp__growth-tools__get_notion_page",
    "mcp__growth-tools__get_eventlog_specs",
    "mcp__growth-tools__search_growth_memory",
    "mcp__growth-tools__get_session_messages",
]

__all__ = [
    "create_eventlog_tools",
    "create_growth_memory_tools",
    "create_notion_tools",
    "create_slack_tools",
    "GROWTH_TOOL_NAMES",
]
