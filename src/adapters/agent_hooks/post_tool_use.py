"""
PostToolUse Hooks for Growth Agent

Captures observations and logs tool execution results.
"""
from typing import Dict, Any
from datetime import datetime, timezone
from loguru import logger


# Module-level dependencies (set during app initialization)
_observation_callback = None


def set_observation_callback(callback):
    """
    Set the callback function for capturing observations.

    The callback should have signature:
        async def callback(session_id, loop_id, tool_name, result, is_error)
    """
    global _observation_callback
    _observation_callback = callback


async def capture_observation(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Capture tool execution results as observations.

    Creates an observation record for each tool execution,
    storing the result in the session's short-term memory.
    """
    tool_name = input_data.get("tool_name", "unknown")
    tool_response = input_data.get("tool_response", {})

    # Get session context
    session_id = context.get("session_id")
    loop_id = context.get("loop_id")

    if not session_id:
        logger.warning("No session_id in context, skipping observation capture")
        return {}

    # Check if response indicates an error
    is_error = False
    if isinstance(tool_response, dict):
        is_error = tool_response.get("is_error", False)
    elif isinstance(tool_response, str):
        is_error = "error" in tool_response.lower()

    # Call the observation callback if set
    if _observation_callback:
        try:
            await _observation_callback(
                session_id=session_id,
                loop_id=loop_id,
                tool_name=tool_name,
                result=tool_response,
                is_error=is_error
            )
            logger.debug(f"Observation captured for {tool_name} in session {session_id}")
        except Exception as e:
            logger.error(f"Failed to capture observation: {e}")

    # Return hook output
    if is_error:
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"Tool {tool_name} returned an error. Consider adjusting your approach."
            }
        }

    return {}


async def audit_log(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Log tool execution results for audit purposes.

    Creates detailed audit logs for compliance and debugging.
    """
    tool_name = input_data.get("tool_name", "unknown")
    tool_response = input_data.get("tool_response", {})

    # Get session context
    session_id = context.get("session_id", "unknown")

    # Determine result status
    status = "success"
    if isinstance(tool_response, dict) and tool_response.get("is_error"):
        status = "error"
    elif isinstance(tool_response, str) and "error" in tool_response.lower():
        status = "error"

    # Extract response summary (truncate for logging)
    response_summary = ""
    if isinstance(tool_response, dict):
        content = tool_response.get("content", [])
        if content and isinstance(content, list) and len(content) > 0:
            first_content = content[0]
            if isinstance(first_content, dict):
                response_summary = first_content.get("text", "")[:200]
    elif isinstance(tool_response, str):
        response_summary = tool_response[:200]

    logger.info(
        f"Tool result: {tool_name} [{status}]",
        extra={
            "tool_name": tool_name,
            "tool_use_id": tool_use_id,
            "session_id": session_id,
            "status": status,
            "response_summary": response_summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    )

    return {}
