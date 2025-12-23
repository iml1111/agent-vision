"""
Sub-Agent Tools for Supervisor

Provides tools that allow the Supervisor to delegate tasks to specialized sub-agents.
Each tool wraps a sub-agent execution and returns results to the Supervisor.
"""
from typing import Any, Callable, Dict, List, Optional

from claude_agent_sdk import tool

from adapters.agent.subagents.base import BaseSubAgent
from adapters.repositories.mongodb.message import MongoMessageRepository
from domain.entities.message import MessageEntity
from domain.value_objects.agent_enums import MessageRole
from domain.value_objects.agent_types import SubAgentExecutionResult
from logging_config import get_logger

logger = get_logger(__name__)


# Tool Descriptions

SLACK_AGENT_DESCRIPTION = """Discover the WHY behind the metrics through team communications.

Data tells you WHAT happened; Slack reveals WHY and what the team thinks about it.

Use when you need:
- Decision context: Why the team chose a direction, what alternatives were considered
- Experiment discussions: Team reactions to A/B tests, feature launches
- User feedback: VoC, complaints, success stories shared in channels
- Problem recognition: Early warnings, concerns raised by team members
- Informal insights: Knowledge that never made it to documentation

Parameters:
- task (required): What context you need. Include time hints if relevant (e.g., "recent", "around launch date").

Examples:
- ask_slack_agent(task="Recent team discussions and concerns about retention drop")
- ask_slack_agent(task="Alternatives the team considered when deciding to redesign onboarding")
"""

PRODUCT_AGENT_DESCRIPTION = """Understand WHY data patterns appear through product context.

Data shows WHAT happened; Product context explains WHY it happened.

Use when you need:
- Release Context: When features launched, what changed (to interpret metric shifts)
- Business Background: Why certain decisions were made
- Roadmap Alignment: How current metrics relate to future plans
- Domain Knowledge: Product-specific terminology and feature relationships

Parameters:
- task (required): What product context you need. Be specific about the feature, timeline, or decision.

Examples:
- ask_product_agent(task="When was the new onboarding flow launched and what changed?")
- ask_product_agent(task="Business background for the credit system redesign")
"""

DATA_AGENT_DESCRIPTION = """Provide quantifiable evidence through EventLog data analysis.

Other agents explain WHY (Slack) or WHAT (Notion); Data agent tells you HOW MUCH, HOW FAST, and WHAT'S THE TREND.

Use when you need:
- Metrics & KPIs: DAU, retention rates, conversion rates, revenue
- Trend analysis: Time-series patterns, growth/decline detection
- Funnel analysis: Step-by-step conversion, drop-off points
- Cohort analysis: D+1, D+7, D+30 retention by user segments
- UTM attribution: Traffic source and campaign performance
- User behavior: Event sequences, engagement patterns

Data source: EventLog collection (Leslie AI platform user events)
- Core fields: event, timestamp, session_id, platform, user_id
- 100+ event types: page views, clicks, scrolls, purchases, etc.

Returns: Results with executed queries for verification and learning.

Parameters:
- task (required): What to analyze. Include time range and specific metrics.

Examples:
- ask_data_agent(task="D+7 retention trend over the last 30 days, weekly comparison")
- ask_data_agent(task="Signup conversion rate by utm_source")
- ask_data_agent(task="Onboarding funnel drop-off rates by step")
"""

MEMORY_AGENT_DESCRIPTION = """Search past Growth sessions for historical insights via RAG.

Use when you need: similar past analyses, proven hypotheses, experiment results, or lessons learned.

Returns structured insights per session:
- problem/bottleneck: What was analyzed and why
- hypotheses/experiment_cards: What was tested
- outcome/learnings: What worked and key takeaways

Parameters:
- task (required): Describe the problem context. Include metric names or feature areas for better matches.

Example: ask_memory_agent(task="Past retention analyses - especially onboarding funnel optimization cases")
"""


# Mapping from agent name to MessageRole
AGENT_NAME_TO_ROLE: Dict[str, MessageRole] = {
    "slack": MessageRole.SUBAGENT_SLACK,
    "product": MessageRole.SUBAGENT_PRODUCT,
    "data": MessageRole.SUBAGENT_DATA,
    "memory": MessageRole.SUBAGENT_MEMORY,
}


def create_subagent_tools(
    subagents: Dict[str, BaseSubAgent],
    message_repo: Optional[MongoMessageRepository] = None,
    session_id: Optional[str] = None,
) -> List[Callable[..., Any]]:
    """
    Create tools that allow Supervisor to call sub-agents.

    Args:
        subagents: Dictionary mapping agent keys to agent instances
            Expected keys: "slack", "product", "data", "memory"
        message_repo: Message repository for saving sub-agent events immediately
        session_id: Session ID for message association

    Returns:
        List of @tool decorated functions for the Supervisor
    """

    async def _save_events(
        agent_name: str,
        tool_name: str,
        result: SubAgentExecutionResult
    ) -> None:
        """Save sub-agent execution events immediately to Message collection."""
        if not message_repo or not session_id:
            logger.warning("Cannot save sub-agent events: message_repo or session_id not set")
            return

        role = AGENT_NAME_TO_ROLE.get(agent_name)
        if not role:
            logger.error(f"Unknown agent name: {agent_name}")
            return

        for seq, event in enumerate(result.events, 1):
            event_type = event.get("type", "unknown")

            if event_type == "text":
                msg = MessageEntity.create(
                    session_id=session_id,
                    role=role,
                    content=event.get("content", ""),
                    metadata={
                        "event_type": "text",
                        "subagent_tool": tool_name,
                        "sequence": seq,
                    }
                )
            elif event_type == "tool_use":
                tool_name_inner = event.get("tool_name", "unknown")
                msg = MessageEntity.create(
                    session_id=session_id,
                    role=role,
                    content=f"Tool: {tool_name_inner}",
                    metadata={
                        "event_type": "tool_use",
                        "subagent_tool": tool_name,
                        "sequence": seq,
                        "tool_name": tool_name_inner,
                        "tool_input": event.get("tool_input"),
                    }
                )
            else:
                # Skip unknown event types
                continue

            try:
                await message_repo.create(msg)
            except Exception as e:
                logger.error(f"Failed to save sub-agent event: {e}")

        logger.debug(
            f"Saved {len(result.events)} events from {agent_name} agent "
            f"(subagent_tool={tool_name})"
        )

    @tool(
        "ask_slack_agent",
        SLACK_AGENT_DESCRIPTION,
        {
            "task": str,
        }
    )
    async def ask_slack_agent(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Slack Agent to retrieve team communications."""
        task = args.get("task", "")

        if not task:
            return {
                "content": [{"type": "text", "text": "Error: task parameter is required"}],
                "is_error": True
            }

        agent = subagents["slack"]

        try:
            async with agent:
                result = await agent.execute(task)
            # Save events immediately
            await _save_events("slack", "ask_slack_agent", result)
            return {"content": [{"type": "text", "text": result.final_response}]}
        except Exception as e:
            logger.error(f"Slack agent execution failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Slack agent error: {str(e)}"}],
                "is_error": True
            }

    @tool(
        "ask_product_agent",
        PRODUCT_AGENT_DESCRIPTION,
        {
            "task": str,
        }
    )
    async def ask_product_agent(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Product Domain Agent to retrieve product knowledge."""
        task = args.get("task", "")

        if not task:
            return {
                "content": [{"type": "text", "text": "Error: task parameter is required"}],
                "is_error": True
            }

        agent = subagents["product"]

        try:
            async with agent:
                result = await agent.execute(task)
            # Save events immediately
            await _save_events("product", "ask_product_agent", result)
            return {"content": [{"type": "text", "text": result.final_response}]}
        except Exception as e:
            logger.error(f"Product domain agent execution failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Product agent error: {str(e)}"}],
                "is_error": True
            }

    @tool(
        "ask_data_agent",
        DATA_AGENT_DESCRIPTION,
        {
            "task": str,
        }
    )
    async def ask_data_agent(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Data Analysis Agent to analyze EventLog data."""
        task = args.get("task", "")

        if not task:
            return {
                "content": [{"type": "text", "text": "Error: task parameter is required"}],
                "is_error": True
            }

        agent = subagents["data"]

        try:
            async with agent:
                result = await agent.execute(task)
            # Save events immediately
            await _save_events("data", "ask_data_agent", result)
            return {"content": [{"type": "text", "text": result.final_response}]}
        except Exception as e:
            logger.error(f"Data analysis agent execution failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Data agent error: {str(e)}"}],
                "is_error": True
            }

    @tool(
        "ask_memory_agent",
        MEMORY_AGENT_DESCRIPTION,
        {
            "task": str,
        }
    )
    async def ask_memory_agent(args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Memory Agent to retrieve historical insights."""
        task = args.get("task", "")

        if not task:
            return {
                "content": [{"type": "text", "text": "Error: task parameter is required"}],
                "is_error": True
            }

        agent = subagents["memory"]

        try:
            async with agent:
                result = await agent.execute(task)
            # Save events immediately
            await _save_events("memory", "ask_memory_agent", result)
            return {"content": [{"type": "text", "text": result.final_response}]}
        except Exception as e:
            logger.error(f"Memory agent execution failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Memory agent error: {str(e)}"}],
                "is_error": True
            }

    return [ask_slack_agent, ask_product_agent, ask_data_agent, ask_memory_agent]


# Tool names for allowed_tools configuration
SUPERVISOR_TOOL_NAMES: List[str] = [
    # Custom sub-agent tools
    "mcp__supervisor-tools__ask_slack_agent",
    "mcp__supervisor-tools__ask_product_agent",
    "mcp__supervisor-tools__ask_data_agent",
    "mcp__supervisor-tools__ask_memory_agent",
    # Built-in tools
    "WebSearch",
    "WebFetch",
    "TodoWrite",
    # External MCP tools
    "mcp__sequential-thinking__sequentialthinking",
]
