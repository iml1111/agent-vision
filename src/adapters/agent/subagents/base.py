"""
Base Sub-Agent Abstract Class

Defines the common interface for all sub-agents in the Growth Hacking system.
Each sub-agent is a specialized, stateless agent that executes tasks delegated by the Supervisor.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Awaitable, Callable, Dict, List, Optional, Type

from claude_agent_sdk import (
    ClaudeSDKClient,
    ClaudeAgentOptions,
    AssistantMessage,
    UserMessage,
    TextBlock,
    ToolUseBlock,
    ToolResultBlock,
    create_sdk_mcp_server,
)

from domain.value_objects.agent_types import SubAgentExecutionResult
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
        allowed_tools = [f"mcp__{self.name}-tools__{tool.name}" for tool in tools]
        allowed_tools.extend(SUBAGENT_BUILTIN_TOOLS)

        return ClaudeAgentOptions(
            mcp_servers={
                f"{self.name}-tools": self._mcp_server,
                "sequential-thinking": {
                    "command": "mcp-server-sequential-thinking",
                    "args": []
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

    async def execute(
        self,
        task: str,
        on_event: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> SubAgentExecutionResult:
        """
        Execute a task and return the result with trace data.

        This is a stateless execution - each call is independent.
        The sub-agent may call multiple tools internally before returning.

        Args:
            task: The task description from the Supervisor.
                  Include specific requirements (e.g., summary vs raw content) in the task.
            on_event: Optional async callback to receive events in real-time.
                      Called with each event dict as it occurs during execution.

        Returns:
            SubAgentExecutionResult containing final response and all internal events
        """
        started_at = datetime.now(timezone.utc)
        events: List[Dict[str, Any]] = []
        response_parts: List[str] = []
        executed_queries: List[Dict[str, Any]] = []
        sequence = 0
        error = None

        try:
            # Build the prompt
            prompt = self._build_prompt(task)

            # Execute the query
            await self._client.query(prompt)

            # Collect all responses and events
            async for message in self._client.receive_response():
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        sequence += 1
                        if isinstance(block, TextBlock):
                            response_parts.append(block.text)
                            event = {
                                "sequence": sequence,
                                "type": "text",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "content": block.text
                            }
                            events.append(event)
                            if on_event:
                                try:
                                    await on_event(event)
                                except Exception as e:
                                    logger.warning(f"on_event callback failed: {e}")
                        elif isinstance(block, ToolUseBlock):
                            # Track tool usage for transparency
                            executed_queries.append({
                                "tool": block.name,
                                "input": block.input,
                            })
                            event = {
                                "sequence": sequence,
                                "type": "tool_use",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "tool_name": block.name,
                                "tool_input": block.input
                            }
                            events.append(event)
                            if on_event:
                                try:
                                    await on_event(event)
                                except Exception as e:
                                    logger.warning(f"on_event callback failed: {e}")
                # UserMessage contains ToolResultBlock with tool execution results
                elif isinstance(message, UserMessage):
                    for block in message.content:
                        if isinstance(block, ToolResultBlock):
                            sequence += 1
                            event = {
                                "sequence": sequence,
                                "type": "tool_result",
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "tool_use_id": block.tool_use_id,
                                "content": block.content,
                                "is_error": block.is_error or False
                            }
                            events.append(event)
                            if on_event:
                                try:
                                    await on_event(event)
                                except Exception as e:
                                    logger.warning(f"on_event callback failed: {e}")

            # Combine response with executed queries for transparency
            final_response = "\n".join(response_parts)

            if executed_queries and self._should_include_queries():
                queries_summary = self._format_executed_queries(executed_queries)
                final_response = f"{final_response}\n\n---\n{queries_summary}"

        except Exception as e:
            logger.error(f"{self.name} execution failed: {e}")
            error = str(e)
            final_response = f"Error: {self.name} failed to execute task - {str(e)}"

        completed_at = datetime.now(timezone.utc)
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

        return SubAgentExecutionResult(
            final_response=final_response,
            events=events,
            started_at=started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            error=error
        )

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
