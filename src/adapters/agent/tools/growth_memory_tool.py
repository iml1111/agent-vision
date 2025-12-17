"""
Growth Memory Tools for Growth Agent

Provides vector search and recent memory retrieval
for RAG (Retrieval-Augmented Generation).
"""
from typing import Any, Dict, List, Optional
from claude_code_sdk import tool
from loguru import logger
from domain.value_objects.agent_enums import GrowthMemoryType


# Module-level dependencies (set during app initialization)
_growth_memory_repo = None
_embedding_client = None


def set_growth_memory_dependencies(growth_memory_repo, embedding_client):
    """Set growth memory repository and embedding client for tool use"""
    global _growth_memory_repo, _embedding_client
    _growth_memory_repo = growth_memory_repo
    _embedding_client = embedding_client


@tool(
    "search_growth_memory",
    "Search for relevant past insights, experiments, and patterns using semantic similarity",
    {
        "query": str,
        "limit": int,
        "memory_type": Optional[str]
    }
)
async def search_growth_memory(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search growth memory using vector similarity.

    Args:
        query: Natural language search query
        limit: Maximum number of results (default 5, max 10)
        memory_type: Optional filter by type ("session_summary", "experiment_result", "insight", "pattern")

    Returns:
        Relevant memories from past sessions and analyses
    """
    if _growth_memory_repo is None or _embedding_client is None:
        return {
            "content": [{"type": "text", "text": "Growth memory dependencies not initialized"}],
            "is_error": True
        }

    query = args.get("query")
    limit = min(args.get("limit", 5), 10)
    memory_type_str = args.get("memory_type")

    if not query:
        return {
            "content": [{"type": "text", "text": "Query is required for memory search"}],
            "is_error": True
        }

    try:
        # Generate embedding for the query
        query_embedding = await _embedding_client.generate_embedding(query)

        # Parse memory type if provided
        memory_type = None
        if memory_type_str:
            try:
                memory_type = GrowthMemoryType(memory_type_str)
            except ValueError:
                return {
                    "content": [{"type": "text", "text": f"Invalid memory_type: {memory_type_str}. Valid types: session_summary, experiment_result, insight, pattern"}],
                    "is_error": True
                }

        # Perform vector search
        memories = await _growth_memory_repo.vector_search(
            query_embedding=query_embedding,
            limit=limit,
            memory_type=memory_type,
            min_score=0.7
        )

        if not memories:
            return {
                "content": [{"type": "text", "text": f"No relevant memories found for: '{query}'"}]
            }

        # Format results
        response_text = f"Found {len(memories)} relevant memories for: '{query}'\n\n"

        for i, memory in enumerate(memories, 1):
            response_text += f"--- Memory {i} ({memory.memory_type.value}) ---\n"
            response_text += f"{memory.content[:500]}{'...' if len(memory.content) > 500 else ''}\n"
            if memory.tags:
                response_text += f"Tags: {', '.join(memory.tags)}\n"
            response_text += f"Created: {memory.created_at.isoformat()}\n\n"

        return {
            "content": [{"type": "text", "text": response_text}]
        }

    except Exception as e:
        logger.error(f"Failed to search growth memory: {e}")
        return {
            "content": [{"type": "text", "text": f"Error searching memory: {str(e)}"}],
            "is_error": True
        }


@tool(
    "get_recent_memories",
    "Get the most recent growth memories",
    {
        "limit": int,
        "memory_type": Optional[str]
    }
)
async def get_recent_memories(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get recent growth memories.

    Args:
        limit: Maximum number of memories to retrieve (default 5, max 10)
        memory_type: Optional filter by type ("session_summary", "experiment_result", "insight", "pattern")

    Returns:
        Recent memories ordered by creation time
    """
    if _growth_memory_repo is None:
        return {
            "content": [{"type": "text", "text": "Growth memory repository not initialized"}],
            "is_error": True
        }

    limit = min(args.get("limit", 5), 10)
    memory_type_str = args.get("memory_type")

    try:
        # Parse memory type if provided
        memory_type = None
        if memory_type_str:
            try:
                memory_type = GrowthMemoryType(memory_type_str)
            except ValueError:
                return {
                    "content": [{"type": "text", "text": f"Invalid memory_type: {memory_type_str}. Valid types: session_summary, experiment_result, insight, pattern"}],
                    "is_error": True
                }

        # Get recent memories
        memories = await _growth_memory_repo.get_recent(
            limit=limit,
            memory_type=memory_type
        )

        if not memories:
            type_filter = f" of type '{memory_type_str}'" if memory_type_str else ""
            return {
                "content": [{"type": "text", "text": f"No recent memories found{type_filter}"}]
            }

        # Format results
        type_filter = f" ({memory_type_str})" if memory_type_str else ""
        response_text = f"Recent {len(memories)} memories{type_filter}:\n\n"

        for i, memory in enumerate(memories, 1):
            response_text += f"--- Memory {i} ({memory.memory_type.value}) ---\n"
            response_text += f"{memory.content[:500]}{'...' if len(memory.content) > 500 else ''}\n"
            if memory.tags:
                response_text += f"Tags: {', '.join(memory.tags)}\n"
            response_text += f"Created: {memory.created_at.isoformat()}\n\n"

        return {
            "content": [{"type": "text", "text": response_text}]
        }

    except Exception as e:
        logger.error(f"Failed to get recent memories: {e}")
        return {
            "content": [{"type": "text", "text": f"Error retrieving memories: {str(e)}"}],
            "is_error": True
        }
