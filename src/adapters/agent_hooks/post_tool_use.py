"""
PostToolUse Hooks for Growth Agent

Logs tool execution results for audit and debugging.
"""
from typing import Dict, Any
from datetime import datetime, timezone

from loguru import logger


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

    # Return error context to agent if tool failed
    if status == "error":
        return {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": f"Tool {tool_name} returned an error. Consider adjusting your approach."
            }
        }

    return {}
