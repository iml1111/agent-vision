"""
Session Lifecycle Hooks for Growth Agent

Handles session end events, including memory summarization.
"""
from typing import Dict, Any, Optional, Callable, Awaitable
from loguru import logger


# Module-level dependencies (set during app initialization)
_memory_summarization_callback: Optional[Callable[[str], Awaitable[None]]] = None


def set_memory_summarization_callback(callback: Callable[[str], Awaitable[None]]):
    """
    Set the callback function for memory summarization.

    The callback should have signature:
        async def callback(session_id: str) -> None
    """
    global _memory_summarization_callback
    _memory_summarization_callback = callback


async def on_session_end(
    session_id: str,
    final_status: str,
    context: Dict[str, Any]
) -> None:
    """
    Handle session end event.

    Triggers memory summarization for completed sessions
    to create long-term memories from the session's observations.

    Args:
        session_id: The ID of the ending session
        final_status: The final status of the session (completed, failed, cancelled)
        context: Additional context about the session
    """
    logger.info(
        f"Session ended: {session_id}",
        extra={
            "session_id": session_id,
            "final_status": final_status,
            "context_keys": list(context.keys())
        }
    )

    # Only summarize completed sessions
    if final_status != "completed":
        logger.info(f"Skipping memory summarization for {final_status} session: {session_id}")
        return

    # Trigger memory summarization
    if _memory_summarization_callback:
        try:
            logger.info(f"Starting memory summarization for session: {session_id}")
            await _memory_summarization_callback(session_id)
            logger.info(f"Memory summarization completed for session: {session_id}")
        except Exception as e:
            logger.error(f"Memory summarization failed for session {session_id}: {e}")
    else:
        logger.warning("Memory summarization callback not set, skipping")


async def on_hitl_timeout(
    session_id: str,
    timeout_seconds: int,
    context: Dict[str, Any]
) -> None:
    """
    Handle HITL timeout event.

    Called when a session waiting for HITL response times out.

    Args:
        session_id: The ID of the timed out session
        timeout_seconds: The timeout duration that was exceeded
        context: Additional context about the session
    """
    logger.warning(
        f"HITL timeout for session: {session_id}",
        extra={
            "session_id": session_id,
            "timeout_seconds": timeout_seconds,
            "hitl_request": context.get("hitl_request")
        }
    )


async def on_loop_limit_reached(
    session_id: str,
    loop_count: int,
    max_loops: int,
    context: Dict[str, Any]
) -> None:
    """
    Handle loop limit reached event.

    Called when a session reaches its maximum loop count.

    Args:
        session_id: The ID of the session
        loop_count: Current loop count
        max_loops: Maximum allowed loops
        context: Additional context about the session
    """
    logger.warning(
        f"Loop limit reached for session: {session_id}",
        extra={
            "session_id": session_id,
            "loop_count": loop_count,
            "max_loops": max_loops
        }
    )
