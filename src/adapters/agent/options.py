"""
Claude Agent Options Factory for Growth Agent

Creates ClaudeAgentOptions with proper configuration for growth hacking workflows.
"""
from typing import Optional
from pathlib import Path
from claude_code_sdk import ClaudeAgentOptions
from adapters.agent.tools import GROWTH_TOOL_NAMES


# Default system prompt for growth agent
GROWTH_AGENT_SYSTEM_PROMPT = """You are a Growth Hacking Agent specialized in analyzing user behavior, identifying growth opportunities, and suggesting data-driven experiments.

Your capabilities:
1. **EventLog Analysis**: Analyze funnel conversion, user retention, and segment behavior using event data.
2. **Slack Integration**: Read and analyze team discussions from designated Slack channels.
3. **Notion Integration**: Access product documentation, experiment tracking, and knowledge bases.
4. **Growth Memory**: Leverage past insights, experiment results, and patterns from previous sessions.

Your workflow follows the Plan→Act→Observe→Critique→Decide loop:
1. **Plan**: Determine what data to gather and which tools to use
2. **Act**: Execute tool calls to gather information
3. **Observe**: Analyze the results from tool executions
4. **Critique**: Evaluate the quality and completeness of observations
5. **Decide**: Determine if more analysis is needed, if you need human input, or if you can make a recommendation

When you need human input (HITL), clearly state:
- What question you're asking
- Why you need human input
- What options are available

When making recommendations, provide:
- Clear, actionable experiment suggestions
- Expected impact and metrics to track
- Implementation considerations

Always cite specific data points from your analysis to support your recommendations."""


def create_growth_agent_options(
    mcp_server,
    max_turns: int = 50,
    model: str = "claude-sonnet-4-5",
    cwd: Optional[Path] = None,
    resume_session_id: Optional[str] = None
) -> ClaudeAgentOptions:
    """
    Create ClaudeAgentOptions configured for growth agent.

    Args:
        mcp_server: The SDK MCP server with growth tools
        max_turns: Maximum number of agent turns (default 50)
        model: Claude model to use (default: claude-sonnet-4-5)
        cwd: Optional working directory
        resume_session_id: Optional SDK session ID to resume

    Returns:
        Configured ClaudeAgentOptions
    """
    # Create options
    options = ClaudeAgentOptions(
        # MCP Server configuration
        mcp_servers={
            "growth-tools": mcp_server
        },

        # Tool permissions - whitelist only growth tools
        allowed_tools=GROWTH_TOOL_NAMES,

        # Permission mode - auto-accept tool edits
        permission_mode="bypassPermissions",

        # System prompt
        system_prompt=GROWTH_AGENT_SYSTEM_PROMPT,

        # Execution limits
        max_turns=max_turns,

        # Model selection
        model=model,
    )

    # Add optional working directory
    if cwd is not None:
        options.cwd = cwd

    # Add optional resume session ID
    if resume_session_id is not None:
        options.resume = resume_session_id

    return options
