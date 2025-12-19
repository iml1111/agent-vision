"""
Slack Sub-Agent

Specialized agent for Slack communication retrieval.
Autonomously selects relevant channels and summarizes or returns raw messages.
"""
from typing import Any, Callable, Dict, List

from adapters.external.slack_client import SlackClient
from adapters.agent.tools.slack_tool import create_slack_tools
from config import Config
from .base import BaseSubAgent


SLACK_AGENT_SYSTEM_PROMPT = """You are the Slack Sub-Agent in a Growth Hacking system.

## Your Role
Find and summarize relevant Slack discussions for the Supervisor.
You must autonomously decide which channels to search based on the task.

## Available Tools
- list_slack_channels: Get available channels with their descriptions
- get_slack_messages: Get messages from a specific channel

## Workflow
1. First, call list_slack_channels to see available channels
2. Based on the task, select the most relevant channel(s)
3. Retrieve messages from selected channels
4. Summarize findings or return raw messages as requested

## Response Format
- Default: Summarize findings concisely with key insights
- If raw content is requested: Include original messages with timestamps and authors
- Always explain your channel selection reasoning
- Highlight relevant quotes or discussions that support the analysis

## Guidelines
- Focus on discussions relevant to the Supervisor's task
- Look for team decisions, concerns, and insights
- If no relevant discussions found, clearly state that
- Consider multiple channels if the topic spans different teams
"""


class SlackAgent(BaseSubAgent):
    """
    Slack sub-agent for team communication retrieval.

    Responsibilities:
    - Autonomously select relevant channels based on task
    - Retrieve and summarize Slack discussions
    - Support both summarized and raw message output
    """

    def __init__(
        self,
        slack_client: SlackClient,
        config: Config,
        model: str = "claude-opus-4-5",
        max_turns: int = 20,
    ) -> None:
        """
        Initialize the Slack agent.

        Args:
            slack_client: Slack API client
            config: Application config for allowlist access
            model: Claude model to use
            max_turns: Maximum number of agent turns
        """
        dependencies = {
            "slack_client": slack_client,
            "config": config,
        }
        super().__init__(dependencies, model, max_turns)

    @property
    def name(self) -> str:
        return "slack-agent"

    @property
    def system_prompt(self) -> str:
        return SLACK_AGENT_SYSTEM_PROMPT

    def create_tools(self) -> List[Callable[..., Any]]:
        """Create Slack tools for this agent."""
        return create_slack_tools(
            slack_client=self._dependencies["slack_client"],
            config=self._dependencies["config"],
        )

    def _should_include_queries(self) -> bool:
        """Slack agent doesn't need to show queries."""
        return False
