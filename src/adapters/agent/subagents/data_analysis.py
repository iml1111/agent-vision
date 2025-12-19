"""
Data Analysis Sub-Agent

Specialized agent for EventLog data analysis.
Executes MongoDB aggregation pipelines and returns results with queries for transparency.
"""
from typing import Any, Callable, Dict, List

from adapters.mongodb.collections.eventlog_adapter import EventLogAdapter
from adapters.external.notion_client import NotionClient
from adapters.agent.tools.eventlog_tool import create_eventlog_tools
from adapters.agent.tools.notion_tool import create_notion_tools
from config import Config
from .base import BaseSubAgent


DATA_ANALYSIS_AGENT_SYSTEM_PROMPT = """You are the Data Analysis Sub-Agent in a Growth Hacking system.

## Your Role
Execute EventLog aggregation queries and return results with the queries used.
You are the expert on data analysis and MongoDB aggregation pipelines.

## Available Tools
- get_eventlog_specs: Get event schema definitions (understand what events and fields exist)
- run_eventlog_aggregation: Execute MongoDB aggregation pipeline on EventLog collection

## Workflow
1. Understand the analysis task from the Supervisor
2. If needed, check get_eventlog_specs to understand available events
3. Design and execute appropriate aggregation pipeline(s)
4. May run multiple queries if needed for comprehensive analysis
5. Return results with all executed queries for transparency

## Response Format
- Present aggregated results clearly with numbers and metrics
- ALWAYS include the executed queries for verification
- Format queries as JSON for readability
- Explain what each query measures
- Highlight key findings and patterns

## Query Design Guidelines
- Always include $limit stage (required for security)
- Use $match early to filter data efficiently
- Consider time ranges with ISODate strings
- Use $group for aggregations, $project for shaping output
- For funnel analysis, use multiple $match stages or $facet

## Example Query Structure
```json
[
  {"$match": {"event": "page_view", "timestamp": {"$gte": "2024-01-01"}}},
  {"$group": {"_id": "$user_id", "count": {"$sum": 1}}},
  {"$sort": {"count": -1}},
  {"$limit": 100}
]
```
"""


class DataAnalysisAgent(BaseSubAgent):
    """
    Data Analysis sub-agent for EventLog aggregation.

    Responsibilities:
    - Execute MongoDB aggregation pipelines on EventLog
    - Provide query transparency for verification
    - Support complex multi-query analyses
    """

    def __init__(
        self,
        eventlog_adapter: EventLogAdapter,
        notion_client: NotionClient,
        config: Config,
        model: str = "claude-opus-4-5",
        max_turns: int = 30,
    ) -> None:
        """
        Initialize the Data Analysis agent.

        Args:
            eventlog_adapter: EventLog MongoDB adapter
            notion_client: Notion client for event specs
            config: Application config
            model: Claude model to use
            max_turns: Maximum number of agent turns
        """
        dependencies = {
            "eventlog_adapter": eventlog_adapter,
            "notion_client": notion_client,
            "config": config,
        }
        super().__init__(dependencies, model, max_turns)

    @property
    def name(self) -> str:
        return "data-analysis-agent"

    @property
    def system_prompt(self) -> str:
        return DATA_ANALYSIS_AGENT_SYSTEM_PROMPT

    def create_tools(self) -> List[Callable[..., Any]]:
        """Create EventLog and Notion (for specs) tools for this agent."""
        tools: List[Callable[..., Any]] = []

        # EventLog aggregation tool
        tools.extend(create_eventlog_tools(
            eventlog_adapter=self._dependencies["eventlog_adapter"],
        ))

        # Notion tools - only need get_eventlog_specs
        notion_tools = create_notion_tools(
            notion_client=self._dependencies["notion_client"],
            config=self._dependencies["config"],
        )
        # Filter to only include get_eventlog_specs
        tools.extend([t for t in notion_tools if t.__name__ == "get_eventlog_specs"])

        return tools

    def _should_include_queries(self) -> bool:
        """Data analysis agent should show executed queries for transparency."""
        return True
