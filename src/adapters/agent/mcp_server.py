"""
MCP Server Factory for Growth Agent

Creates an in-process SDK MCP server with all growth tools registered.
"""
from claude_code_sdk import create_sdk_mcp_server
from adapters.agent_tools import GROWTH_TOOLS


def create_growth_agent_mcp_server():
    """
    Create the Growth Agent MCP server with all registered tools.

    This creates an in-process MCP server that provides:
    - EventLog analysis tools (funnel, retention, segment)
    - Slack integration tools (list channels, get messages)
    - Notion integration tools (list resources, query database, get page)
    - Growth Memory tools (vector search, recent memories)

    Returns:
        SDK MCP server instance configured with growth tools
    """
    server = create_sdk_mcp_server(
        name="growth-tools",
        version="1.0.0",
        tools=GROWTH_TOOLS
    )

    return server
