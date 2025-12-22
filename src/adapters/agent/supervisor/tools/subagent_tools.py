"""
Sub-Agent Tools for Supervisor

Provides tools that allow the Supervisor to delegate tasks to specialized sub-agents.
Each tool wraps a sub-agent execution and returns results to the Supervisor.
"""
from typing import Any, Callable, Dict, List, Optional

from claude_agent_sdk import tool

from adapters.agent.subagents.base import BaseSubAgent
from domain.entities.subagent_trace import SubAgentTraceEntity
from domain.ports.subagent_trace import SubAgentTraceRepository
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


def create_subagent_tools(
    subagents: Dict[str, BaseSubAgent],
    trace_repo: Optional[SubAgentTraceRepository] = None,
    session_id: Optional[str] = None,
    parent_message_id_getter: Optional[Callable[[], Optional[str]]] = None,
) -> List[Callable[..., Any]]:
    """
    Create tools that allow Supervisor to call sub-agents.

    Args:
        subagents: Dictionary mapping agent keys to agent instances
            Expected keys: "slack", "product", "data", "memory"
        trace_repo: Repository for saving sub-agent traces (optional)
        session_id: Parent session ID for trace association (optional)
        parent_message_id_getter: Callable to get current parent message ID (optional)

    Returns:
        List of @tool decorated functions for the Supervisor
    """

    async def _save_trace(
        agent_name: str,
        task: str,
        result: SubAgentExecutionResult,
        model: Optional[str] = None
    ) -> None:
        """Save sub-agent execution trace to database."""
        parent_msg_id = parent_message_id_getter()

        try:
            trace = SubAgentTraceEntity.create(
                session_id=session_id,
                parent_message_id=parent_msg_id,
                agent_name=agent_name,
                task=task,
                events=result.events,
                result=result.final_response,
                started_at=result.started_at,
                completed_at=result.completed_at,
                duration_ms=result.duration_ms,
                model=model,
                error=result.error
            )
            await trace_repo.create(trace)
            logger.debug(f"Saved trace for {agent_name} agent")
        except Exception as e:
            logger.error(f"Failed to save trace for {agent_name}: {e}")

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
            await _save_trace("slack", task, result, agent._model)
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
            await _save_trace("product", task, result, agent._model)
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
            await _save_trace("data", task, result, agent._model)
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
            await _save_trace("memory", task, result, agent._model)
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
