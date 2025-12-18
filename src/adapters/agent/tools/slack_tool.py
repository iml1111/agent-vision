"""
Slack Tools for Growth Agent

Provides Slack channel listing and message retrieval
with allowlist enforcement.
"""
from typing import Any, Dict, List, Optional
from logging_config import get_logger

from claude_code_sdk import tool

logger = get_logger(__name__)


# Module-level dependencies (set during app initialization)
_slack_client = None
_config = None


def set_slack_dependencies(slack_client, config):
    """Set Slack client and config for tool use"""
    global _slack_client, _config
    _slack_client = slack_client
    _config = config


@tool(
    "list_slack_channels",
    "List available Slack channels from the allowlist",
    {}
)
async def list_slack_channels(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List Slack channels available in the allowlist.

    Returns:
        List of allowed Slack channels with their IDs and descriptions
    """
    if _config is None:
        return {
            "content": [{"type": "text", "text": "Config not initialized"}],
            "is_error": True
        }

    try:
        channels = _config.slack_channels

        if not channels:
            return {
                "content": [{"type": "text", "text": "No Slack channels configured in allowlist"}]
            }

        response_text = "Available Slack Channels:\n"
        for channel in channels:
            desc = f" - {channel.description}" if channel.description else ""
            response_text += f"- #{channel.channel_name} (ID: {channel.channel_id}){desc}\n"

        return {
            "content": [{"type": "text", "text": response_text}]
        }

    except Exception as e:
        logger.error(f"Failed to list Slack channels: {e}")
        return {
            "content": [{"type": "text", "text": f"Error listing channels: {str(e)}"}],
            "is_error": True
        }


@tool(
    "get_slack_messages",
    "Get messages from a Slack channel (must be in allowlist)",
    {
        "channel_id": str,
        "limit": int,
        "oldest": Optional[str],
        "latest": Optional[str]
    }
)
async def get_slack_messages(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get messages from a Slack channel.

    Args:
        channel_id: Slack channel ID (must be in allowlist)
        limit: Maximum number of messages to retrieve (default 50, max 100)
        oldest: Only messages after this Unix timestamp
        latest: Only messages before this Unix timestamp

    Returns:
        Messages from the channel
    """
    if _slack_client is None or _config is None:
        return {
            "content": [{"type": "text", "text": "Slack dependencies not initialized"}],
            "is_error": True
        }

    channel_id = args.get("channel_id")
    limit = min(args.get("limit", 50), 100)
    oldest = args.get("oldest")
    latest = args.get("latest")

    # Allowlist check (server-side enforcement)
    if not _config.is_slack_channel_allowed(channel_id):
        return {
            "content": [{"type": "text", "text": f"Access denied: Channel {channel_id} is not in the allowlist"}],
            "is_error": True
        }

    try:
        result = await _slack_client.get_messages(
            channel_id=channel_id,
            limit=limit,
            oldest=oldest,
            latest=latest
        )

        messages = result.get("messages", [])

        if not messages:
            return {
                "content": [{"type": "text", "text": "No messages found in the specified range"}]
            }

        # Format messages for response
        channel_info = _config.get_slack_channel_info(channel_id)
        channel_name = channel_info.channel_name if channel_info else channel_id

        response_text = f"Messages from #{channel_name} ({len(messages)} messages):\n\n"

        for msg in messages[:limit]:
            user = msg.get("user", "unknown")
            text = msg.get("text", "")[:500]  # Truncate long messages
            ts = msg.get("ts", "")
            response_text += f"[{ts}] {user}: {text}\n\n"

        if result.get("has_more"):
            response_text += "\n(More messages available - use pagination to retrieve)"

        return {
            "content": [{"type": "text", "text": response_text}]
        }

    except Exception as e:
        logger.error(f"Failed to get Slack messages: {e}")
        return {
            "content": [{"type": "text", "text": f"Error retrieving messages: {str(e)}"}],
            "is_error": True
        }
