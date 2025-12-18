"""
Slack Tools for Growth Agent

Provides Slack channel listing and message retrieval.
"""
from typing import Any, Callable, Dict, List, Optional
from logging_config import get_logger

from claude_code_sdk import tool

from adapters.external.slack_client import SlackClient
from config import Config

logger = get_logger(__name__)


def create_slack_tools(slack_client: SlackClient, config: Config) -> List[Callable[..., Any]]:
    """
    Create Slack tools with injected dependencies.

    Args:
        slack_client: Slack API client
        config: Application config for allowlist access

    Returns:
        List of @tool decorated functions
    """

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
        channels = config.slack_channels

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

    @tool(
        "get_slack_messages",
        "Get messages from a Slack channel",
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
            channel_id: Slack channel ID
            limit: Maximum number of messages to retrieve (default 50, max 100)
            oldest: Only messages after this Unix timestamp
            latest: Only messages before this Unix timestamp

        Returns:
            Messages from the channel
        """
        channel_id = args.get("channel_id")
        limit = min(args.get("limit", 50), 100)
        oldest = args.get("oldest")
        latest = args.get("latest")

        try:
            result = await slack_client.get_messages(
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

            channel_info = config.get_slack_channel_info(channel_id)
            channel_name = channel_info.channel_name if channel_info else channel_id

            response_text = f"Messages from #{channel_name} ({len(messages)} messages):\n\n"

            for msg in messages[:limit]:
                user = msg.get("user", "unknown")
                text = msg.get("text", "")[:500]
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

    return [list_slack_channels, get_slack_messages]
