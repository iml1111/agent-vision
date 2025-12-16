"""
Growth Agent Client

High-level wrapper for Claude SDK client with session lifecycle management.
"""
from typing import AsyncIterator, Dict, Any, Optional
from claude_code_sdk import ClaudeSDKClient, AssistantMessage, TextBlock, ToolUseBlock
from loguru import logger
from .mcp_server import create_growth_agent_mcp_server
from .options import create_growth_agent_options


class GrowthAgentClient:
    """
    Growth Agent client wrapper.

    Provides a high-level interface for interacting with the Claude Agent SDK,
    managing session lifecycle and message handling.
    """

    def __init__(
        self,
        max_turns: int = 50,
        max_budget_usd: Optional[float] = None,
        model: str = "claude-sonnet-4-5"
    ):
        """
        Initialize the Growth Agent client.

        Args:
            max_turns: Maximum number of agent turns per query
            max_budget_usd: Optional budget limit in USD
            model: Claude model to use
        """
        self._max_turns = max_turns
        self._max_budget_usd = max_budget_usd
        self._model = model
        self._mcp_server = None
        self._options = None
        self._client: Optional[ClaudeSDKClient] = None
        self._session_context: Dict[str, Any] = {}

    def set_session_context(self, context: Dict[str, Any]):
        """Set session context for hooks"""
        self._session_context = context

    async def __aenter__(self) -> "GrowthAgentClient":
        """Async context manager entry"""
        # Create MCP server
        self._mcp_server = create_growth_agent_mcp_server()

        # Create options with session context
        self._options = create_growth_agent_options(
            mcp_server=self._mcp_server,
            max_turns=self._max_turns,
            max_budget_usd=self._max_budget_usd,
            model=self._model,
            session_context=self._session_context
        )

        # Create and enter client context
        self._client = ClaudeSDKClient(options=self._options)
        await self._client.__aenter__()

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
        self._client = None
        self._options = None
        self._mcp_server = None

    async def query(self, prompt: str) -> None:
        """
        Send a query to the agent.

        Args:
            prompt: The prompt/query to send

        Note:
            Use receive_response() to get the agent's response after querying.
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        await self._client.query(prompt)

    async def receive_response(self) -> AsyncIterator[Any]:
        """
        Receive responses from the agent.

        Yields:
            Response messages from the agent (AssistantMessage, ToolUseBlock, etc.)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        async for message in self._client.receive_response():
            yield message

    async def run_query(
        self,
        prompt: str,
        on_message: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Run a complete query and collect responses.

        Args:
            prompt: The prompt/query to send
            on_message: Optional callback for each message

        Returns:
            Dict with:
                - text_response: Final text response from the agent
                - tool_calls: List of tool calls made
                - messages: All messages received
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        await self.query(prompt)

        text_response = ""
        tool_calls = []
        messages = []

        async for message in self.receive_response():
            messages.append(message)

            if on_message:
                try:
                    on_message(message)
                except Exception as e:
                    logger.warning(f"on_message callback error: {e}")

            if isinstance(message, AssistantMessage):
                for block in message.content:
                    if isinstance(block, TextBlock):
                        text_response = block.text
                    elif isinstance(block, ToolUseBlock):
                        tool_calls.append({
                            "id": block.id,
                            "name": block.name,
                            "input": block.input
                        })

        return {
            "text_response": text_response,
            "tool_calls": tool_calls,
            "messages": messages
        }


async def run_growth_agent_query(
    prompt: str,
    session_context: Optional[Dict[str, Any]] = None,
    max_turns: int = 50,
    model: str = "claude-sonnet-4-5"
) -> Dict[str, Any]:
    """
    Convenience function to run a single growth agent query.

    Args:
        prompt: The prompt/query to send
        session_context: Optional context for the session
        max_turns: Maximum number of agent turns
        model: Claude model to use

    Returns:
        Dict with text_response, tool_calls, and messages
    """
    async with GrowthAgentClient(max_turns=max_turns, model=model) as client:
        if session_context:
            client.set_session_context(session_context)
        return await client.run_query(prompt)
