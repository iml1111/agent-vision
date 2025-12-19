"""
GrowthMemory Tool for Growth Agent

Provides semantic search over past Growth cases using Atlas Vector Search.
Enables RAG-based retrieval of similar historical analyses.
"""
import json
from typing import Any, Callable, Dict, List, Optional

from claude_code_sdk import tool
from logging_config import get_logger

from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.repositories.mongodb.growth_memory import MongoGrowthMemoryRepository
from adapters.repositories.mongodb.message import MongoMessageRepository
from domain.entities.growth_memory import GrowthMemoryEntity
from domain.entities.message import MessageEntity

logger = get_logger(__name__)


TOOL_DESCRIPTION = """Search similar past Growth cases from memory.

Use this tool to find historical Growth analyses that are similar to the current problem.
Returns past cases with their problem definitions, bottlenecks, hypotheses, and outcomes.

## When to Use
- At the start of a new Growth analysis to learn from similar past cases
- When looking for proven hypotheses or experiment designs
- When comparing current findings with historical patterns

## Response Format
Returns a list of similar cases, each containing:
- problem: Problem definition from the past case
- bottleneck: Identified bottleneck and evidence
- hypotheses: List of hypotheses (adopted and rejected)
- outcome: Results and conclusions
- learnings: Key learnings and next actions

## Example Query
"Retention drop for new users in the first week after signup"
"Low conversion rate in checkout funnel for mobile users"
"""


GET_MESSAGES_DESCRIPTION = """Get conversation history from a past Growth session.

Use this tool to retrieve the actual messages exchanged during a past session.
Call this after search_growth_memory to see the full conversation details.

## Parameters
- session_id (required): Session ID from search_growth_memory results
- limit (optional): Max messages to return (default: 50, max: 100)

## Response Format
Returns the session's conversation history with:
- session_id: The queried session ID
- message_count: Number of messages returned
- messages: List of messages with role, content, and timestamp
"""


def _format_memory_for_response(memory: GrowthMemoryEntity) -> Dict[str, Any]:
    """Format a GrowthMemoryEntity for tool response"""
    return {
        "session_id": memory.session_id,
        "problem": memory.problem_snapshot,
        "bottleneck": memory.bottleneck_evidence,
        "hypotheses": memory.hypotheses,
        "outcome": memory.outcome,
        "learnings": memory.learnings_next_actions,
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
    }


def _format_message_for_response(message: MessageEntity) -> Dict[str, Any]:
    """Format a MessageEntity for tool response"""
    return {
        "role": message.role.value,
        "content": message.content,
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }


def create_growth_memory_tools(
    memory_repo: MongoGrowthMemoryRepository,
    embedding_client: OpenAIEmbeddingClient,
    message_repo: MongoMessageRepository,
) -> List[Callable[..., Any]]:
    """
    Create GrowthMemory search tools with injected dependencies.

    Args:
        memory_repo: GrowthMemory repository for vector search
        embedding_client: OpenAI client for query embedding generation
        message_repo: Message repository for session conversation retrieval

    Returns:
        List of @tool decorated functions
    """

    @tool(
        "search_growth_memory",
        TOOL_DESCRIPTION,
        {
            "query": str,
            "limit": Optional[int],
        }
    )
    async def search_growth_memory(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Search similar Growth cases by semantic similarity.

        Args:
            query: Problem description or search query
            limit: Maximum number of results (default: 3, max: 10)

        Returns:
            List of similar past Growth cases
        """
        query = args.get("query", "")
        limit = min(args.get("limit", 3), 10)  # Cap at 10

        if not query or not query.strip():
            return {
                "content": [{"type": "text", "text": "Error: query parameter is required"}],
                "is_error": True
            }

        try:
            # Generate query embedding
            query_vector = await embedding_client.generate_embedding(query)

            # Search similar memories
            memories = await memory_repo.vector_search(
                query_vector=query_vector,
                limit=limit,
            )

            if not memories:
                return {
                    "content": [{
                        "type": "text",
                        "text": "No similar Growth cases found. This might be a new type of problem."
                    }]
                }

            # Format results
            formatted_memories = [_format_memory_for_response(m) for m in memories]
            result_text = f"Found {len(memories)} similar Growth case(s):\n\n"
            result_text += json.dumps(formatted_memories, indent=2, ensure_ascii=False)

            return {
                "content": [{"type": "text", "text": result_text}]
            }

        except Exception as e:
            logger.error(f"GrowthMemory search failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Search error: {str(e)}"}],
                "is_error": True
            }

    @tool(
        "get_session_messages",
        GET_MESSAGES_DESCRIPTION,
        {
            "session_id": str,
            "limit": Optional[int],
        }
    )
    async def get_session_messages(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get conversation history from a past Growth session.

        Args:
            session_id: Session ID from search_growth_memory results
            limit: Maximum number of messages to return (default: 50, max: 100)

        Returns:
            Session conversation history with messages
        """
        session_id = args.get("session_id", "")
        limit = min(args.get("limit", 50), 100)  # Cap at 100

        if not session_id or not session_id.strip():
            return {
                "content": [{"type": "text", "text": "Error: session_id parameter is required"}],
                "is_error": True
            }

        try:
            messages = await message_repo.get_by_session_id(
                session_id=session_id,
                limit=limit,
            )

            if not messages:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"No messages found for session {session_id}. The session may not exist or has no messages."
                    }]
                }

            formatted_messages = [_format_message_for_response(m) for m in messages]
            result = {
                "session_id": session_id,
                "message_count": len(messages),
                "messages": formatted_messages,
            }
            result_text = f"Found {len(messages)} message(s) for session {session_id}:\n\n"
            result_text += json.dumps(result, indent=2, ensure_ascii=False)

            return {
                "content": [{"type": "text", "text": result_text}]
            }

        except Exception as e:
            logger.error(f"Failed to get session messages: {e}")
            return {
                "content": [{"type": "text", "text": f"Error retrieving messages: {str(e)}"}],
                "is_error": True
            }

    return [search_growth_memory, get_session_messages]
