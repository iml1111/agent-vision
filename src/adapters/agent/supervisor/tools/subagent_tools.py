"""
Sub-Agent Tools for Supervisor

Provides tools that allow the Supervisor to delegate tasks to specialized sub-agents.
Each tool wraps a sub-agent execution and returns results to the Supervisor.
"""
from typing import Any, Callable, Dict, List

from claude_agent_sdk import tool
from logging_config import get_logger

from adapters.agent.subagents.base import BaseSubAgent

logger = get_logger(__name__)


# Tool Descriptions

SLACK_AGENT_DESCRIPTION = """Delegate task to Slack Agent for team communication retrieval.

The Slack Agent will:
- Autonomously select relevant channels based on the task
- Search and retrieve Slack messages
- Summarize or return raw messages based on task requirements

Parameters:
- task (required): Description of what information to find. Specify if you need raw messages or summary.

Example: call_slack(task="Find discussions about retention drop last week and summarize key points")
"""

PRODUCT_AGENT_DESCRIPTION = """Delegate task to Product Domain Agent for product knowledge.

The Product Domain Agent will:
- Search Notion documentation for relevant information
- Provide product context, features, and timelines
- Summarize or return full content based on task requirements

Parameters:
- task (required): Description of what product context is needed. Specify if you need full content or summary.

Example: call_product(task="Get context on the onboarding flow and summarize recent changes")
"""

DATA_AGENT_DESCRIPTION = """Delegate task to Data Analysis Agent for EventLog analysis.

The Data Analysis Agent will:
- Design and execute MongoDB aggregation pipelines
- May run multiple queries for comprehensive analysis
- Return results WITH executed queries for verification

Parameters:
- task (required): Description of the analysis to perform

Example: call_data(task="Analyze D+7 retention trend for last 30 days")
"""

MEMORY_AGENT_DESCRIPTION = """Delegate task to Growth Memory Agent for historical insights.

The Growth Memory Agent will:
- Search past Growth sessions via RAG (vector search)
- Retrieve full conversation history from relevant sessions
- Return insights WITH executed search queries for verification

Parameters:
- task (required): Description of what historical context is needed

Example: call_memory(task="Find past analyses related to checkout funnel optimization")
"""


def create_subagent_tools(
    subagents: Dict[str, BaseSubAgent],
) -> List[Callable[..., Any]]:
    """
    Create tools that allow Supervisor to call sub-agents.

    Args:
        subagents: Dictionary mapping agent keys to agent instances
            Expected keys: "slack", "product", "data", "memory"

    Returns:
        List of @tool decorated functions for the Supervisor
    """

    @tool(
        "call_slack",
        SLACK_AGENT_DESCRIPTION,
        {
            "task": str,
        }
    )
    async def call_slack(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Slack Agent to retrieve team communications."""
        task = args.get("task", "")

        if not task:
            return {
                "content": [{"type": "text", "text": "Error: task parameter is required"}],
                "is_error": True
            }

        agent = subagents.get("slack")
        if not agent:
            return {
                "content": [{"type": "text", "text": "Error: Slack agent not available"}],
                "is_error": True
            }

        try:
            async with agent:
                result = await agent.execute(task)
            return {"content": [{"type": "text", "text": result}]}
        except Exception as e:
            logger.error(f"Slack agent execution failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Slack agent error: {str(e)}"}],
                "is_error": True
            }

    @tool(
        "call_product",
        PRODUCT_AGENT_DESCRIPTION,
        {
            "task": str,
        }
    )
    async def call_product(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Product Domain Agent to retrieve product knowledge."""
        task = args.get("task", "")

        if not task:
            return {
                "content": [{"type": "text", "text": "Error: task parameter is required"}],
                "is_error": True
            }

        agent = subagents.get("product")
        if not agent:
            return {
                "content": [{"type": "text", "text": "Error: Product domain agent not available"}],
                "is_error": True
            }

        try:
            async with agent:
                result = await agent.execute(task)
            return {"content": [{"type": "text", "text": result}]}
        except Exception as e:
            logger.error(f"Product domain agent execution failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Product agent error: {str(e)}"}],
                "is_error": True
            }

    @tool(
        "call_data",
        DATA_AGENT_DESCRIPTION,
        {
            "task": str,
        }
    )
    async def call_data(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Data Analysis Agent to analyze EventLog data."""
        task = args.get("task", "")

        if not task:
            return {
                "content": [{"type": "text", "text": "Error: task parameter is required"}],
                "is_error": True
            }

        agent = subagents.get("data")
        if not agent:
            return {
                "content": [{"type": "text", "text": "Error: Data analysis agent not available"}],
                "is_error": True
            }

        try:
            async with agent:
                result = await agent.execute(task)
            return {"content": [{"type": "text", "text": result}]}
        except Exception as e:
            logger.error(f"Data analysis agent execution failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Data agent error: {str(e)}"}],
                "is_error": True
            }

    @tool(
        "call_memory",
        MEMORY_AGENT_DESCRIPTION,
        {
            "task": str,
        }
    )
    async def call_memory(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Memory Agent to retrieve historical insights."""
        task = args.get("task", "")

        if not task:
            return {
                "content": [{"type": "text", "text": "Error: task parameter is required"}],
                "is_error": True
            }

        agent = subagents.get("memory")
        if not agent:
            return {
                "content": [{"type": "text", "text": "Error: Memory agent not available"}],
                "is_error": True
            }

        try:
            async with agent:
                result = await agent.execute(task)
            return {"content": [{"type": "text", "text": result}]}
        except Exception as e:
            logger.error(f"Memory agent execution failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Memory agent error: {str(e)}"}],
                "is_error": True
            }

    return [call_slack, call_product, call_data, call_memory]


# Tool names for allowed_tools configuration
SUPERVISOR_TOOL_NAMES: List[str] = [
    # Custom sub-agent tools
    "mcp__supervisor-tools__call_slack",
    "mcp__supervisor-tools__call_product",
    "mcp__supervisor-tools__call_data",
    "mcp__supervisor-tools__call_memory",
    # Built-in tools
    "WebSearch",
    "WebFetch",
    "TodoWrite",
]
