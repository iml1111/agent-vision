"""Agent Tools for MCP Server"""
from .eventlog_tool import funnel_analysis, retention_analysis, segment_analysis
from .slack_tool import list_slack_channels, get_slack_messages
from .notion_tool import list_notion_resources, query_notion_database, get_notion_page

# All available tools for the growth agent
GROWTH_TOOLS = [
    # EventLog tools
    funnel_analysis,
    retention_analysis,
    segment_analysis,
    # Slack tools
    list_slack_channels,
    get_slack_messages,
    # Notion tools
    list_notion_resources,
    query_notion_database,
    get_notion_page,
]

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
    "GROWTH_TOOLS",
    "GROWTH_TOOL_NAMES",
    "funnel_analysis",
    "retention_analysis",
    "segment_analysis",
    "list_slack_channels",
    "get_slack_messages",
    "list_notion_resources",
    "query_notion_database",
    "get_notion_page",
]
