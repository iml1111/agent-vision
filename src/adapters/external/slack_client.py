"""
Slack Client Adapter

Provides Slack API operations for message retrieval and channel info.
"""
from typing import Optional, Dict, Any, List
from logging_config import get_logger

from adapters.http.client import HTTPClient
from domain.exceptions import SlackAPIError

logger = get_logger(__name__)


class SlackClient(HTTPClient):
    """
    Slack API client

    Extends HTTPClient with Slack-specific operations.
    Uses Bot token authentication.
    """

    BASE_URL = "https://slack.com/api"

    def __init__(self, bot_token: str, timeout: float = 30.0):
        """
        Initialize Slack client

        Args:
            bot_token: Slack Bot OAuth token (xoxb-...)
            timeout: Request timeout in seconds
        """
        super().__init__(
            base_url=self.BASE_URL,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {bot_token}",
                "Content-Type": "application/json; charset=utf-8"
            }
        )

    async def _check_response(self, response: Dict[str, Any], operation: str) -> Dict[str, Any]:
        """Check Slack API response for errors"""
        if not response.get("ok", False):
            error = response.get("error", "unknown_error")
            logger.error(f"Slack API error in {operation}: {error}")
            raise SlackAPIError(f"Slack API {operation} failed: {error}")
        return response

    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """
        Get channel information

        Args:
            channel_id: Slack channel ID (C...)

        Returns:
            Channel information dict

        Raises:
            SlackAPIError: If API call fails
        """
        try:
            response = await self.get(
                "conversations.info",
                params={"channel": channel_id}
            )
            await self._check_response(response, "conversations.info")
            return response.get("channel", {})

        except SlackAPIError:
            raise
        except Exception as e:
            logger.error(f"Failed to get channel info: {e}")
            raise SlackAPIError(f"Failed to get channel info: {e}") from e

    async def get_messages(
        self,
        channel_id: str,
        limit: int = 100,
        oldest: Optional[str] = None,
        latest: Optional[str] = None,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get messages from a channel

        Args:
            channel_id: Slack channel ID (C...)
            limit: Maximum number of messages to return (default 100, max 1000)
            oldest: Only messages after this Unix timestamp
            latest: Only messages before this Unix timestamp
            cursor: Pagination cursor for next page

        Returns:
            Dict with messages list and pagination info

        Raises:
            SlackAPIError: If API call fails
        """
        params = {
            "channel": channel_id,
            "limit": min(limit, 1000)
        }
        if oldest:
            params["oldest"] = oldest
        if latest:
            params["latest"] = latest
        if cursor:
            params["cursor"] = cursor

        try:
            response = await self.get("conversations.history", params=params)
            await self._check_response(response, "conversations.history")

            return {
                "messages": response.get("messages", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("response_metadata", {}).get("next_cursor")
            }

        except SlackAPIError:
            raise
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            raise SlackAPIError(f"Failed to get messages: {e}") from e

    async def list_channels(
        self,
        types: str = "public_channel,private_channel",
        limit: int = 100,
        cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        List available channels

        Args:
            types: Comma-separated channel types
            limit: Maximum number of channels to return
            cursor: Pagination cursor

        Returns:
            Dict with channels list and pagination info

        Raises:
            SlackAPIError: If API call fails
        """
        params = {
            "types": types,
            "limit": min(limit, 1000)
        }
        if cursor:
            params["cursor"] = cursor

        try:
            response = await self.get("conversations.list", params=params)
            await self._check_response(response, "conversations.list")

            return {
                "channels": response.get("channels", []),
                "next_cursor": response.get("response_metadata", {}).get("next_cursor")
            }

        except SlackAPIError:
            raise
        except Exception as e:
            logger.error(f"Failed to list channels: {e}")
            raise SlackAPIError(f"Failed to list channels: {e}") from e
