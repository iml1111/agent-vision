"""
PreToolUse Hooks for Growth Agent

Provides access control and logging before tool execution.
Server-side enforcement of allowlist policies.
"""
from typing import Dict, Any
from logging_config import get_logger

logger = get_logger(__name__)


# Module-level dependencies (set during app initialization)
_config = None


def set_hook_dependencies(config):
    """Set dependencies for hooks (config includes allowlist functionality)"""
    global _config
    _config = config


async def validate_slack_allowlist(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate Slack channel access against allowlist.

    Blocks tool execution if the channel is not in the allowlist.
    """
    tool_name = input_data.get("tool_name", "")

    # Only validate Slack tools
    if "slack" not in tool_name.lower():
        return {}

    tool_input = input_data.get("tool_input", {})
    channel_id = tool_input.get("channel_id")

    if not channel_id:
        return {}

    if _config is None:
        logger.warning("Config not initialized, denying Slack access")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Config not available"
            }
        }

    if not _config.is_slack_channel_allowed(channel_id):
        logger.warning(f"Slack channel access denied: {channel_id}")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"Channel '{channel_id}' is not in the allowlist"
            }
        }

    logger.debug(f"Slack channel access allowed: {channel_id}")
    return {}


async def validate_notion_allowlist(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Validate Notion resource access against allowlist.

    Blocks tool execution if the database/page is not in the allowlist.
    """
    tool_name = input_data.get("tool_name", "")

    # Only validate Notion tools
    if "notion" not in tool_name.lower():
        return {}

    tool_input = input_data.get("tool_input", {})
    database_id = tool_input.get("database_id")
    page_id = tool_input.get("page_id")

    if _config is None:
        logger.warning("Config not initialized, denying Notion access")
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "Config not available"
            }
        }

    # Check database access
    if database_id:
        if not _config.is_notion_database_allowed(database_id):
            logger.warning(f"Notion database access denied: {database_id}")
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Database '{database_id}' is not in the allowlist"
                }
            }

    # Check page access
    if page_id:
        if not _config.is_notion_page_allowed(page_id):
            logger.warning(f"Notion page access denied: {page_id}")
            return {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": f"Page '{page_id}' is not in the allowlist"
                }
            }

    logger.debug(f"Notion access allowed: database={database_id}, page={page_id}")
    return {}


async def log_tool_call(
    input_data: Dict[str, Any],
    tool_use_id: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Log tool calls for audit purposes.

    Does not block execution, only logs.
    """
    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})

    # Get session ID from context if available
    session_id = context.get("session_id", "unknown")

    tool_input_keys = list(tool_input.keys())
    logger.info(
        f"Tool call: {tool_name} | session_id={session_id} | "
        f"tool_use_id={tool_use_id} | input_keys={tool_input_keys}"
    )

    return {}
