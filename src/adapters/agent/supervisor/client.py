"""
Supervisor Agent Client

High-level wrapper for the Growth Hacking Supervisor agent.
Coordinates sub-agents to analyze growth problems.
"""
from types import TracebackType
from typing import Any, AsyncIterator, Dict, List, Optional, Tuple, Type

from claude_agent_sdk import (
    ClaudeSDKClient,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    create_sdk_mcp_server,
)
from logging_config import get_logger

from adapters.external.notion_client import NotionClient
from adapters.external.slack_client import SlackClient
from adapters.mongodb.collections.eventlog_adapter import EventLogAdapter
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.repositories.mongodb.growth_memory import MongoGrowthMemoryRepository
from adapters.repositories.mongodb.message import MongoMessageRepository
from config import Config
from domain.entities.message import MessageEntity
from domain.value_objects import AgentMessageType, ToolCallVO, AgentStreamEvent
from domain.value_objects.agent_enums import MessageRole
from domain.value_objects.agent_types import SubAgentExecutionResult

from adapters.agent.subagents import (
    DataAnalysisAgent,
    MemoryAgent,
    ProductDomainAgent,
    SlackAgent,
)
from .options import create_supervisor_options
from .tools import create_subagent_tools

logger = get_logger(__name__)

# Mapping from agent name to MessageRole
AGENT_NAME_TO_ROLE: Dict[str, MessageRole] = {
    "slack": MessageRole.SUBAGENT_SLACK,
    "product": MessageRole.SUBAGENT_PRODUCT,
    "data": MessageRole.SUBAGENT_DATA,
    "memory": MessageRole.SUBAGENT_MEMORY,
}


class SupervisorAgentClient:
    """
    Supervisor Agent client wrapper.

    Coordinates specialized sub-agents to analyze growth problems.
    The Supervisor can only call sub-agents - it cannot access external APIs directly.

    Sub-Agents:
    - SlackAgent: Team communication retrieval
    - ProductDomainAgent: Product knowledge from Notion
    - DataAnalysisAgent: EventLog data analysis
    - MemoryAgent: Historical insights from past sessions
    """

    def __init__(
        self,
        eventlog_adapter: EventLogAdapter,
        slack_client: SlackClient,
        notion_client: NotionClient,
        config: Config,
        memory_repo: MongoGrowthMemoryRepository,
        embedding_client: OpenAIEmbeddingClient,
        message_repo: MongoMessageRepository,
        model: str = "claude-opus-4-5",
        resume_session_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the Supervisor Agent client.

        Args:
            eventlog_adapter: EventLog collection adapter for Data Analysis agent
            slack_client: Slack API client for Slack agent
            notion_client: Notion API client for Product Domain agent
            config: Application config for allowlist access
            memory_repo: GrowthMemory repository for Memory agent
            embedding_client: OpenAI client for query embedding
            message_repo: Message repository for saving sub-agent events
            model: Claude model to use (default: claude-opus-4-5)
            resume_session_id: Optional SDK session ID to resume
            session_id: Session ID for message association
        """
        # Store context for saving sub-agent events
        self._message_repo = message_repo
        self._session_id = session_id
        # FIFO queue for pending sub-agent results (agent_name, result)
        self._pending_results: List[Tuple[str, SubAgentExecutionResult]] = []

        # Create sub-agents with their dependencies
        self._subagents: Dict[str, Any] = {
            "slack": SlackAgent(
                slack_client=slack_client,
                config=config,
                model=model,
            ),
            "product": ProductDomainAgent(
                notion_client=notion_client,
                config=config,
                model=model,
            ),
            "data": DataAnalysisAgent(
                eventlog_adapter=eventlog_adapter,
                notion_client=notion_client,
                config=config,
                model=model,
            ),
            "memory": MemoryAgent(
                memory_repo=memory_repo,
                embedding_client=embedding_client,
                message_repo=message_repo,
                model=model,
            ),
        }

        # Create tools that wrap sub-agent execution
        # Events are collected via callback, saved later when parent_message_id is known
        tools = create_subagent_tools(
            self._subagents,
            event_collector=lambda name, result: self._pending_results.append((name, result)),
        )

        # Create MCP server with sub-agent tools
        self._mcp_server = create_sdk_mcp_server(
            name="supervisor-tools",
            version="1.0.0",
            tools=tools,
        )

        # Create Supervisor options
        self._options = create_supervisor_options(
            mcp_server=self._mcp_server,
            max_turns=100,
            model=model,
            resume_session_id=resume_session_id,
        )

        self._client: Optional[ClaudeSDKClient] = None
        self._claude_session_id: Optional[str] = None

    @property
    def claude_session_id(self) -> Optional[str]:
        """Get the Claude session ID captured from the response."""
        return self._claude_session_id

    async def __aenter__(self) -> "SupervisorAgentClient":
        """Async context manager entry."""
        self._client = ClaudeSDKClient(options=self._options)
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

    async def query(self, prompt: str) -> None:
        """
        Send a query to the Supervisor agent.

        Args:
            prompt: The prompt/query to send
        """
        await self._client.query(prompt)

    async def receive_response(self) -> AsyncIterator[Any]:
        """
        Receive responses from the Supervisor agent.

        Yields:
            Response messages from the agent
        """
        async for message in self._client.receive_response():
            yield message

    def _parse_message_to_event(self, message: Any) -> Optional[AgentStreamEvent]:
        """Convert SDK message to AgentStreamEvent."""
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

    async def _save_subagent_events(
        self,
        agent_name: str,
        parent_message_id: str,
        result: SubAgentExecutionResult
    ) -> None:
        """
        Save sub-agent execution events as individual Message documents.

        Args:
            agent_name: Name of the sub-agent (slack, product, data, memory)
            parent_message_id: The tool_call.id of the subagent_call message
            result: SubAgentExecutionResult containing events
        """
        if not self._message_repo or not self._session_id:
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
                    session_id=self._session_id,
                    role=role,
                    content=event.get("content", ""),
                    metadata={
                        "event_type": "text",
                        "parent_message_id": parent_message_id,
                        "sequence": seq,
                    }
                )
            elif event_type == "tool_use":
                tool_name = event.get("tool_name", "unknown")
                msg = MessageEntity.create(
                    session_id=self._session_id,
                    role=role,
                    content=f"Tool: {tool_name}",
                    metadata={
                        "event_type": "tool_use",
                        "parent_message_id": parent_message_id,
                        "sequence": seq,
                        "tool_name": tool_name,
                        "tool_input": event.get("tool_input"),
                    }
                )
            else:
                # Skip unknown event types
                continue

            try:
                await self._message_repo.create(msg)
            except Exception as e:
                logger.error(f"Failed to save sub-agent event: {e}")

        logger.debug(
            f"Saved {len(result.events)} events from {agent_name} agent "
            f"(parent_message_id={parent_message_id})"
        )

    async def stream_query(self, prompt: str) -> AsyncIterator[AgentStreamEvent]:
        """
        Execute query in streaming mode.

        Args:
            prompt: The prompt/query to send

        Yields:
            AgentStreamEvent: Each response event in real-time
        """
        await self.query(prompt)

        async for message in self.receive_response():
            event = self._parse_message_to_event(message)
            if event:
                # When TOOL_USE event is received, save the pending sub-agent events
                # SDK executes tools BEFORE yielding events, so results are in queue
                # Use FIFO order to match results with events
                if event.type == AgentMessageType.TOOL_USE and event.tool_call:
                    if self._pending_results:
                        agent_name, result = self._pending_results.pop(0)  # FIFO
                        await self._save_subagent_events(
                            agent_name,
                            event.tool_call.id,
                            result
                        )
                yield event

        # Completion event
        yield AgentStreamEvent(
            type=AgentMessageType.COMPLETE,
            claude_session_id=self._claude_session_id
        )
