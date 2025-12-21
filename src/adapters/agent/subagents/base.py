"""
Base Sub-Agent Abstract Class

Defines the common interface for all sub-agents in the Growth Hacking system.
Each sub-agent is a specialized, stateless agent that executes tasks delegated by the Supervisor.
"""
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Any, Callable, Dict, List, Optional, Type

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
)
from logging_config import get_logger

logger = get_logger(__name__)

# Built-in tools available to all sub-agents
SUBAGENT_BUILTIN_TOOLS = [
    "WebSearch",
    "WebFetch",
    "TodoWrite",
    "mcp__sequential-thinking__sequentialthinking",
]


class BaseSubAgent(ABC):
    """
    Abstract base class for sub-agents.

    Sub-agents are specialized agents that:
    - Execute specific tasks delegated by the Supervisor
    - Have access to a limited set of tools
    - Run stateless (no session persistence)
    - Return results to the Supervisor for synthesis

    Each sub-agent must implement:
    - name: Unique identifier for the agent
    - system_prompt: Instructions defining the agent's role and behavior
    - create_tools(): Factory method to create the agent's tools
    """

    def __init__(
        self,
        dependencies: Dict[str, Any],
        model: str = "claude-opus-4-5",
        max_turns: int = 30,
    ) -> None:
        """
        Initialize the sub-agent.

        Args:
            dependencies: Dictionary of dependencies needed by the agent's tools
            model: Claude model to use (default: claude-opus-4-5)
            max_turns: Maximum number of agent turns (default: 30)
        """
        self._dependencies = dependencies
        self._model = model
        self._max_turns = max_turns
        self._client: Optional[ClaudeSDKClient] = None
        self._mcp_server: Optional[Any] = None

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this sub-agent."""
        ...

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt defining the agent's role and behavior."""
        ...

    @abstractmethod
    def create_tools(self) -> List[Callable[..., Any]]:
        """
        Create the tools available to this sub-agent.

        Returns:
            List of @tool decorated functions
        """
        ...

    def _create_options(self) -> ClaudeAgentOptions:
        """Create ClaudeAgentOptions for this sub-agent."""
        tools = self.create_tools()
        self._mcp_server = create_sdk_mcp_server(
            name=f"{self.name}-tools",
            version="1.0.0",
            tools=tools,
        )

        # Combine MCP tool names with built-in tools
        allowed_tools = [f"mcp__{self.name}-tools__{tool.__name__}" for tool in tools]
        allowed_tools.extend(SUBAGENT_BUILTIN_TOOLS)

        return ClaudeAgentOptions(
            mcp_servers={
                f"{self.name}-tools": self._mcp_server,
                "sequential-thinking": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
                }
            },
            allowed_tools=allowed_tools,
            permission_mode="bypassPermissions",
            system_prompt=self.system_prompt,
            max_turns=self._max_turns,
            model=self._model,
        )

    async def __aenter__(self) -> "BaseSubAgent":
        """Async context manager entry."""
        options = self._create_options()
        self._client = ClaudeSDKClient(options=options)
        await self._client.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

    async def execute(self, task: str) -> str:
        """
        Execute a task and return the final response.

        This is a stateless execution - each call is independent.
        The sub-agent may call multiple tools internally before returning.

        Args:
            task: The task description from the Supervisor.
                  Include specific requirements (e.g., summary vs raw content) in the task.

        Returns:
            The final response text to return to the Supervisor
        """
        if not self._client:
            raise RuntimeError(
                f"{self.name}: Client not initialized. Use 'async with' context manager."
            )

        try:
            # Build the prompt
            prompt = self._build_prompt(task)

            # Execute the query
            await self._client.query(prompt)

            # Collect all text responses
            response_parts: List[str] = []
            executed_queries: List[Dict[str, Any]] = []

            async for message in self._client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            response_parts.append(block.text)
                        elif isinstance(block, ToolUseBlock):
                            # Track tool usage for transparency
                            executed_queries.append({
                                "tool": block.name,
                                "input": block.input,
                            })

            # Combine response with executed queries for transparency
            final_response = "\n".join(response_parts)

            if executed_queries and self._should_include_queries():
                queries_summary = self._format_executed_queries(executed_queries)
                final_response = f"{final_response}\n\n---\n{queries_summary}"

            return final_response

        except Exception as e:
            logger.error(f"{self.name} execution failed: {e}")
            return f"Error: {self.name} failed to execute task - {str(e)}"

    def _build_prompt(self, task: str) -> str:
        """
        Build the prompt for the task.

        Can be overridden by sub-agents that need custom prompt formatting.

        Args:
            task: The task description

        Returns:
            The formatted prompt
        """
        return task

    def _should_include_queries(self) -> bool:
        """
        Whether to include executed queries in the response.

        Override in sub-agents that should show query transparency
        (e.g., DataAnalysisAgent, MemoryAgent).

        Returns:
            True if queries should be included in response
        """
        return False

    def _format_executed_queries(self, queries: List[Dict[str, Any]]) -> str:
        """
        Format executed queries for transparency.

        Args:
            queries: List of executed tool calls

        Returns:
            Formatted string of queries
        """
        if not queries:
            return ""

        lines = ["**Executed Queries:**"]
        for i, q in enumerate(queries, 1):
            lines.append(f"{i}. `{q['tool']}`: {q['input']}")
        return "\n".join(lines)
