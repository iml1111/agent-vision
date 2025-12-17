"""
Growth Agent Client

High-level wrapper for Claude SDK client with session lifecycle management.
"""
from typing import AsyncIterator, Any, Optional, List, Callable
from claude_code_sdk import ClaudeSDKClient, AssistantMessage, TextBlock, ToolUseBlock
from loguru import logger
from domain.value_objects import (
    AgentMessageType,
    ToolCallVO,
    AgentStreamEvent,
    AgentResponse,
)
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
        model: str = "claude-sonnet-4-5",
        resume_session_id: Optional[str] = None
    ):
        """
        Initialize the Growth Agent client.

        Args:
            max_turns: Maximum number of agent turns per query
            max_budget_usd: Optional budget limit in USD
            model: Claude model to use
            resume_session_id: Optional SDK session ID to resume
        """
        self._max_turns = max_turns
        self._max_budget_usd = max_budget_usd
        self._model = model
        self._resume_session_id = resume_session_id
        self._mcp_server = None
        self._options = None
        self._client: Optional[ClaudeSDKClient] = None
        self._sdk_session_id: Optional[str] = None

    @property
    def sdk_session_id(self) -> Optional[str]:
        """Get the SDK session ID captured from the response"""
        return self._sdk_session_id

    async def __aenter__(self) -> "GrowthAgentClient":
        """Async context manager entry"""
        # Create MCP server
        self._mcp_server = create_growth_agent_mcp_server()

        # Create options with resume support
        self._options = create_growth_agent_options(
            mcp_server=self._mcp_server,
            max_turns=self._max_turns,
            max_budget_usd=self._max_budget_usd,
            model=self._model,
            resume_session_id=self._resume_session_id
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

    def _parse_message_to_event(self, message: Any) -> Optional[AgentStreamEvent]:
        """Convert SDK message to AgentStreamEvent"""
        # Init message handling
        if hasattr(message, 'subtype') and message.subtype == 'init':
            if hasattr(message, 'data') and isinstance(message.data, dict):
                session_id = message.data.get('session_id')
                if session_id:
                    self._sdk_session_id = session_id
                    logger.debug(f"Captured SDK session ID: {session_id}")
                    return AgentStreamEvent(
                        type=AgentMessageType.INIT,
                        sdk_session_id=session_id
                    )
        # Also try to capture from session_id attribute directly
        elif hasattr(message, 'session_id') and message.session_id:
            if not self._sdk_session_id:
                self._sdk_session_id = message.session_id
                logger.debug(f"Captured SDK session ID from message: {message.session_id}")

        # AssistantMessage handling
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    return AgentStreamEvent(
                        type=AgentMessageType.TEXT,
                        content=block.text
                    )
                elif isinstance(block, ToolUseBlock):
                    return AgentStreamEvent(
                        type=AgentMessageType.TOOL_USE,
                        tool_call=ToolCallVO(
                            id=block.id,
                            name=block.name,
                            input=block.input
                        )
                    )

        return None

    async def stream_query(
        self,
        prompt: str
    ) -> AsyncIterator[AgentStreamEvent]:
        """
        Execute query in streaming mode.

        Args:
            prompt: The prompt/query to send

        Yields:
            AgentStreamEvent: Each response event in real-time
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        await self.query(prompt)

        async for message in self.receive_response():
            event = self._parse_message_to_event(message)
            if event:
                yield event

        # Completion event
        yield AgentStreamEvent(
            type=AgentMessageType.COMPLETE,
            sdk_session_id=self._sdk_session_id
        )

    async def run_query(
        self,
        prompt: str,
        on_event: Optional[Callable[[AgentStreamEvent], None]] = None
    ) -> AgentResponse:
        """
        Execute query and return final aggregated response.

        Args:
            prompt: The prompt/query to send
            on_event: Optional callback for each event (for real-time updates)

        Returns:
            AgentResponse: Final aggregated response (immutable)
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use 'async with' context manager.")

        text_response = ""
        tool_calls: List[ToolCallVO] = []
        message_count = 0

        async for event in self.stream_query(prompt):
            message_count += 1

            if on_event:
                try:
                    on_event(event)
                except Exception as e:
                    logger.warning(f"on_event callback error: {e}")

            if event.type == AgentMessageType.TEXT:
                text_response = event.content or ""
            elif event.type == AgentMessageType.TOOL_USE and event.tool_call:
                tool_calls.append(event.tool_call)

        return AgentResponse(
            text_response=text_response,
            tool_calls=tuple(tool_calls),
            sdk_session_id=self._sdk_session_id,
            message_count=message_count
        )
