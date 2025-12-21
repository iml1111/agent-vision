"""
Slack Tools for Growth Agent

Provides Slack channel listing and message retrieval.
"""
from typing import Any, Callable, Dict, List, Optional

from claude_agent_sdk import tool

from adapters.external.slack_client import SlackClient
from config import Config
from logging_config import get_logger

logger = get_logger(__name__)


def _extract_block_text(blocks: List[Dict[str, Any]]) -> str:
    """Extract text content from Slack blocks (minimized, no JSON)"""
    texts = []
    for block in blocks:
        block_type = block.get("type")

        if block_type == "rich_text":
            for element in block.get("elements", []):
                for item in element.get("elements", []):
                    if item.get("type") == "text":
                        texts.append(item.get("text", ""))
                    elif item.get("type") == "link":
                        link_text = item.get("text") or item.get("url", "")
                        texts.append(f"[{link_text}]")

        elif block_type == "section":
            text_obj = block.get("text", {})
            if text_obj:
                texts.append(text_obj.get("text", ""))

        elif block_type == "header":
            text_obj = block.get("text", {})
            if text_obj:
                texts.append(f"**{text_obj.get('text', '')}**")

        elif block_type == "context":
            for elem in block.get("elements", []):
                if elem.get("type") == "mrkdwn":
                    texts.append(elem.get("text", ""))

    return " ".join(filter(None, texts))


def _format_attachments(attachments: List[Dict[str, Any]]) -> str:
    """Format attachments as brief link info"""
    links = []
    for att in attachments:
        title = att.get("title") or att.get("fallback") or "Link"
        url = att.get("title_link") or att.get("original_url") or ""
        if url:
            links.append(f"[{title}]({url})")
        elif title:
            links.append(f"[{title}]")
    return " | ".join(links) if links else ""


def _format_files(files: List[Dict[str, Any]]) -> str:
    """Format files as brief link info"""
    file_info = []
    for f in files:
        name = f.get("name") or f.get("title") or "File"
        url = f.get("permalink") or f.get("url_private") or ""
        if url:
            file_info.append(f"[{name}]({url})")
        else:
            file_info.append(name)
    return " | ".join(file_info) if file_info else ""


def _format_message(msg: Dict[str, Any], indent: str = "") -> str:
    """Format a single Slack message with optional indentation for thread replies"""
    user = msg.get("user") or msg.get("bot_id") or "unknown"
    text = msg.get("text", "")[:500]
    ts = msg.get("ts", "")

    result = f"{indent}[{ts}] {user}: {text}\n"

    # Block text (if contains additional info beyond text)
    if "blocks" in msg:
        block_text = _extract_block_text(msg["blocks"])
        if block_text and block_text not in text:
            result += f"{indent}  [blocks]: {block_text[:300]}\n"

    # Attachments (link previews)
    if "attachments" in msg:
        att_text = _format_attachments(msg["attachments"])
        if att_text:
            result += f"{indent}  [links]: {att_text}\n"

    # Files
    if "files" in msg:
        file_text = _format_files(msg["files"])
        if file_text:
            result += f"{indent}  [files]: {file_text}\n"

    return result


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
        """List available Slack channels from the allowlist.

Returns a list of allowed channels with:
- channel_name: Channel display name (e.g., #growth-data)
- channel_id: Slack channel ID (use with get_slack_messages)
- description: Channel purpose/description

Use this to discover available channels before calling get_slack_messages.""",
        {}
    )
    async def list_slack_channels(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        List Slack channels available in the allowlist.

        Returns:
            List of allowed Slack channels with their IDs and descriptions
        """
        channels = config.slack_channels

        response_text = "Available Slack Channels:\n"
        for channel in channels:
            desc = f" - {channel.description}" if channel.description else ""
            response_text += f"- #{channel.channel_name} (ID: {channel.channel_id}){desc}\n"

        return {
            "content": [{"type": "text", "text": response_text}]
        }

    @tool(
        "get_slack_messages",
        """Get messages from a Slack channel.

## Parameters
- channel_id (required): Slack channel ID (e.g., "C0123456789")
- limit (optional): Max messages to return (default: 50, max: 100)
- oldest (optional): Only messages after this Unix timestamp (e.g., "1234567890.123456")
- latest (optional): Only messages before this Unix timestamp

## Response Format
Returns messages with:
- ts: Message timestamp
- user: User ID who sent the message
- text: Message content (truncated to 500 chars)

## Example
get_slack_messages(channel_id="C0123456789", limit=20)""",
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
                ts = msg.get("ts", "")

                # Skip if this is a reply that was broadcast to channel
                # (it will be shown under its parent thread)
                thread_ts = msg.get("thread_ts")
                is_reply = thread_ts and thread_ts != ts
                if is_reply:
                    continue

                # Format the main message
                response_text += _format_message(msg)

                # Fetch and display thread replies if any
                reply_count = msg.get("reply_count", 0)
                if reply_count > 0:
                    response_text += f"  [thread: {reply_count} replies]\n"
                    try:
                        thread_result = await slack_client.get_thread_replies(
                            channel_id=channel_id,
                            thread_ts=ts,
                            limit=50  # Limit thread replies
                        )
                        replies = thread_result.get("messages", [])
                        for reply in replies:
                            response_text += _format_message(reply, indent="    ")
                    except Exception as thread_err:
                        logger.warning(f"Failed to fetch thread replies: {thread_err}")

                response_text += "\n"

            if result.get("has_more"):
                response_text += "(More messages available - use pagination to retrieve)"

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
