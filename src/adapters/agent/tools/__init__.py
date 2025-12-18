"""Agent Tools Factory Functions"""
from .eventlog_tool import create_eventlog_tools
from .slack_tool import create_slack_tools
from .notion_tool import create_notion_tools

# Tool names for allowed_tools configuration
GROWTH_TOOL_NAMES = [
    "mcp__growth-tools__funnel_analysis",
    "mcp__growth-tools__retention_analysis",
    "mcp__growth-tools__segment_analysis",
    "mcp__growth-tools__list_slack_channels",
    "mcp__growth-tools__get_slack_messages",
    "mcp__growth-tools__list_notion_resources",
    "mcp__growth-tools__query_notion_database",
    "mcp__growth-tools__get_notion_page",
]

__all__ = [
    "create_eventlog_tools",
    "create_slack_tools",
    "create_notion_tools",
    "GROWTH_TOOL_NAMES",
]
