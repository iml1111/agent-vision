"""
Growth Agent Client

High-level wrapper for Claude SDK client with session lifecycle management.
"""
from typing import AsyncIterator, Any, Optional
from logging_config import get_logger

from claude_code_sdk import ClaudeSDKClient, AssistantMessage, TextBlock, ToolUseBlock, create_sdk_mcp_server
from domain.value_objects import (
    AgentMessageType,
    ToolCallVO,
    AgentStreamEvent,
)
from .options import create_growth_agent_options
from .tools import GROWTH_TOOLS

logger = get_logger(__name__)


class GrowthAgentClient:
    """
    Growth Agent client wrapper.

    Provides a high-level interface for interacting with the Claude Agent SDK,
    managing session lifecycle and message handling.
    """

    _MAX_TURNS = 100

    def __init__(
        self,
        model: str = "claude-opus-4-5",
        resume_session_id: Optional[str] = None
    ):
        """
        Initialize the Growth Agent client.

        Args:
            model: Claude model to use
            resume_session_id: Optional SDK session ID to resume
        """
        self._mcp_server = create_sdk_mcp_server(
            name="growth-tools",
            version="1.0.0",
            tools=GROWTH_TOOLS
        )
        self._options = create_growth_agent_options(
            mcp_server=self._mcp_server,
            max_turns=self._MAX_TURNS,
            model=model,
            resume_session_id=resume_session_id
        )
        self._client: Optional[ClaudeSDKClient] = None
        self._claude_session_id: Optional[str] = None

    @property
    def claude_session_id(self) -> Optional[str]:
        """Get the Claude session ID captured from the response"""
        return self._claude_session_id

    async def __aenter__(self) -> "GrowthAgentClient":
        """Async context manager entry"""
        self._client = ClaudeSDKClient(options=self._options)
        await self._client.__aenter__()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._client:
            await self._client.__aexit__(exc_type, exc_val, exc_tb)
            self._client = None

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
                    self._claude_session_id = session_id
                    logger.debug(f"Captured Claude session ID: {session_id}")
                    return AgentStreamEvent(
                        type=AgentMessageType.INIT,
                        claude_session_id=session_id
                    )
        # Also try to capture from session_id attribute directly
        elif hasattr(message, 'session_id') and message.session_id:
            if not self._claude_session_id:
                self._claude_session_id = message.session_id
                logger.debug(f"Captured Claude session ID from message: {message.session_id}")

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
            claude_session_id=self._claude_session_id
        )
