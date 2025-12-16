"""
Allowlist Configuration for External Integrations

Server-side enforcement of Slack/Notion resource access.
Configured via JSON environment variables.
"""
import json
from typing import List, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SlackChannelAllowlistItem(BaseModel):
    """Slack channel allowlist item"""
    channel_id: str
    channel_name: str
    description: Optional[str] = None


class NotionDatabaseAllowlistItem(BaseModel):
    """Notion database allowlist item"""
    database_id: str
    database_name: str
    description: Optional[str] = None


class NotionPageAllowlistItem(BaseModel):
    """Notion page allowlist item"""
    page_id: str
    page_name: str
    description: Optional[str] = None


class AllowlistConfig(BaseSettings):
    """
    Allowlist Configuration for Slack and Notion resources.

    Environment Variables:
        SLACK_CHANNEL_ALLOWLIST: JSON array of SlackChannelAllowlistItem
        NOTION_DATABASE_ALLOWLIST: JSON array of NotionDatabaseAllowlistItem
        NOTION_PAGE_ALLOWLIST: JSON array of NotionPageAllowlistItem

    Example:
        SLACK_CHANNEL_ALLOWLIST='[{"channel_id": "C123", "channel_name": "general"}]'
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Raw JSON strings from environment
    slack_channel_allowlist_json: str = Field(
        default="[]",
        validation_alias="SLACK_CHANNEL_ALLOWLIST"
    )
    notion_database_allowlist_json: str = Field(
        default="[]",
        validation_alias="NOTION_DATABASE_ALLOWLIST"
    )
    notion_page_allowlist_json: str = Field(
        default="[]",
        validation_alias="NOTION_PAGE_ALLOWLIST"
    )

    @property
    def slack_channels(self) -> List[SlackChannelAllowlistItem]:
        """Parse and return Slack channel allowlist"""
        try:
            items = json.loads(self.slack_channel_allowlist_json)
            return [SlackChannelAllowlistItem(**item) for item in items]
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def notion_databases(self) -> List[NotionDatabaseAllowlistItem]:
        """Parse and return Notion database allowlist"""
        try:
            items = json.loads(self.notion_database_allowlist_json)
            return [NotionDatabaseAllowlistItem(**item) for item in items]
        except (json.JSONDecodeError, TypeError):
            return []

    @property
    def notion_pages(self) -> List[NotionPageAllowlistItem]:
        """Parse and return Notion page allowlist"""
        try:
            items = json.loads(self.notion_page_allowlist_json)
            return [NotionPageAllowlistItem(**item) for item in items]
        except (json.JSONDecodeError, TypeError):
            return []

    def is_slack_channel_allowed(self, channel_id: str) -> bool:
        """Check if a Slack channel is in the allowlist"""
        allowed_ids = {item.channel_id for item in self.slack_channels}
        return channel_id in allowed_ids

    def is_notion_database_allowed(self, database_id: str) -> bool:
        """Check if a Notion database is in the allowlist"""
        # Normalize ID (remove dashes for comparison)
        normalized_id = database_id.replace("-", "")
        allowed_ids = {item.database_id.replace("-", "") for item in self.notion_databases}
        return normalized_id in allowed_ids

    def is_notion_page_allowed(self, page_id: str) -> bool:
        """Check if a Notion page is in the allowlist"""
        # Normalize ID (remove dashes for comparison)
        normalized_id = page_id.replace("-", "")
        allowed_ids = {item.page_id.replace("-", "") for item in self.notion_pages}
        return normalized_id in allowed_ids

    def get_slack_channel_info(self, channel_id: str) -> Optional[SlackChannelAllowlistItem]:
        """Get Slack channel info by ID"""
        for item in self.slack_channels:
            if item.channel_id == channel_id:
                return item
        return None

    def get_notion_database_info(self, database_id: str) -> Optional[NotionDatabaseAllowlistItem]:
        """Get Notion database info by ID"""
        normalized_id = database_id.replace("-", "")
        for item in self.notion_databases:
            if item.database_id.replace("-", "") == normalized_id:
                return item
        return None

    def get_notion_page_info(self, page_id: str) -> Optional[NotionPageAllowlistItem]:
        """Get Notion page info by ID"""
        normalized_id = page_id.replace("-", "")
        for item in self.notion_pages:
            if item.page_id.replace("-", "") == normalized_id:
                return item
        return None
