"""
Growth Memory Sub-Agent

Specialized agent for RAG-based historical insights retrieval.
Searches past Growth sessions and provides advice based on historical patterns.
"""
from typing import Any, Callable, Dict, List

from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.repositories.mongodb.growth_memory import MongoGrowthMemoryRepository
from adapters.repositories.mongodb.message import MongoMessageRepository
from adapters.agent.tools.growth_memory_tool import create_growth_memory_tools
from .base import BaseSubAgent


MEMORY_AGENT_SYSTEM_PROMPT = """You are the Growth Memory Sub-Agent in a Growth Hacking system.

## Your Role
Search past Growth sessions and provide insights from historical analyses.
You are the expert on learning from past experiences and patterns.

## Available Tools
- search_growth_memory: Vector search for similar past Growth cases (RAG)
- get_session_messages: Get full conversation history from a past session

## Workflow
1. Understand what historical context the Supervisor needs
2. Use search_growth_memory to find similar past cases
3. If relevant cases found, use get_session_messages to get full details
4. May run multiple searches with different queries for comprehensive coverage
5. Return insights with executed queries for transparency

## Response Format
- Summarize relevant past insights and patterns
- ALWAYS include executed search queries for verification
- Highlight successful approaches from past sessions
- Note any failed experiments and lessons learned
- Provide actionable advice based on historical patterns

## Guidelines
- Focus on insights that are directly applicable to the current task
- If past cases had clear outcomes, emphasize what worked and what didn't
- Consider multiple search angles if the topic is broad
- If no relevant history exists, clearly state that this may be a new problem type
- Look for patterns across multiple past sessions

## Search Strategy
- Start with the core problem description
- Try alternative phrasings if initial search yields few results
- Look for both successful and unsuccessful past approaches
"""


class MemoryAgent(BaseSubAgent):
    """
    Memory sub-agent for historical Growth case retrieval.

    Responsibilities:
    - Search past Growth sessions via RAG
    - Provide insights from historical analyses
    - Advise based on past patterns and outcomes
    """

    def __init__(
        self,
        memory_repo: MongoGrowthMemoryRepository,
        embedding_client: OpenAIEmbeddingClient,
        message_repo: MongoMessageRepository,
        model: str = "claude-opus-4-5",
        max_turns: int = 20,
    ) -> None:
        """
        Initialize the Memory agent.

        Args:
            memory_repo: GrowthMemory repository for RAG search
            embedding_client: OpenAI client for query embedding
            message_repo: Message repository for session retrieval
            model: Claude model to use
            max_turns: Maximum number of agent turns
        """
        dependencies = {
            "memory_repo": memory_repo,
            "embedding_client": embedding_client,
            "message_repo": message_repo,
        }
        super().__init__(dependencies, model, max_turns)

    @property
    def name(self) -> str:
        return "memory-agent"

    @property
    def system_prompt(self) -> str:
        return MEMORY_AGENT_SYSTEM_PROMPT

    def create_tools(self) -> List[Callable[..., Any]]:
        """Create GrowthMemory tools for this agent."""
        return create_growth_memory_tools(
            memory_repo=self._dependencies["memory_repo"],
            embedding_client=self._dependencies["embedding_client"],
            message_repo=self._dependencies["message_repo"],
        )

    def _should_include_queries(self) -> bool:
        """Memory agent should show executed queries for transparency."""
        return True
