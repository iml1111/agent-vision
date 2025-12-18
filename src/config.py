"""
Application Configuration

Pydantic BaseSettings for environment variable management.
"""
import json
import os
from typing import List, Optional

from pydantic import BaseModel, Field, AliasChoices
from pydantic_settings import BaseSettings, SettingsConfigDict

from __about__ import __version__, __author__, __app_name__


# =============================================================================
# Constants
# =============================================================================

# SQS Long Polling wait time (seconds)
SQS_WAIT_TIME_SECONDS = 20

# Project paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
ALLOWLIST_FILE = os.path.join(BASE_DIR, "allowlist.json")


# =============================================================================
# Allowlist Item Models
# =============================================================================


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


class Config(BaseSettings):
    """Application Configuration"""

    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application metadata
    app_name: str = __app_name__
    version: str = __version__
    description: str = "VOID is a Vibe-Oriented In-Domain Design framework."
    contact_name: str = __author__
    contact_url: str = "https://github.com/iml1111"
    contact_email: str = "shin10256@gmail.com"

    # Environment
    environment: str = Field(..., validation_alias=AliasChoices('ENV', 'env'))

    # Database
    mongodb_uri: str = Field(..., validation_alias=AliasChoices('MONGODB_URI', 'mongodb_uri'))
    mongodb_name: str = Field(..., validation_alias=AliasChoices('MONGODB_NAME', 'mongodb_name'))

    # AWS
    aws_access_key_id: str = Field(..., validation_alias=AliasChoices('AWS_ACCESS_KEY_ID', 'aws_access_key_id'))
    aws_secret_access_key: str = Field(..., validation_alias=AliasChoices('AWS_SECRET_ACCESS_KEY', 'aws_secret_access_key'))
    aws_region: str = Field(..., validation_alias=AliasChoices('AWS_REGION', 'aws_region'))

    # AWS SQS (Queue Worker)
    sqs_queue_url: str = Field(..., validation_alias=AliasChoices('SQS_QUEUE_URL', 'sqs_queue_url'))

    # Claude Agent SDK
    anthropic_api_key: str = Field(..., validation_alias=AliasChoices('ANTHROPIC_API_KEY', 'anthropic_api_key'))

    # OpenAI (Embeddings)
    openai_api_key: str = Field(..., validation_alias=AliasChoices('OPENAI_API_KEY', 'openai_api_key'))

    # External Integrations
    slack_bot_token: str = Field(..., validation_alias=AliasChoices('SLACK_BOT_TOKEN', 'slack_bot_token'))
    notion_api_key: str = Field(..., validation_alias=AliasChoices('NOTION_API_KEY', 'notion_api_key'))

    # =========================================================================
    # Allowlist Properties (loaded from JSON file)
    # =========================================================================

    def _load_allowlist(self) -> dict:
        """Load allowlist from JSON file"""
        if not os.path.exists(ALLOWLIST_FILE):
            return {}
        with open(ALLOWLIST_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    @property
    def slack_channels(self) -> List[SlackChannelAllowlistItem]:
        """Load and return Slack channel allowlist from JSON file"""
        try:
            data = self._load_allowlist()
            items = data.get("slack_channels", [])
            return [SlackChannelAllowlistItem(**item) for item in items]
        except (json.JSONDecodeError, TypeError, KeyError):
            return []

    @property
    def notion_databases(self) -> List[NotionDatabaseAllowlistItem]:
        """Load and return Notion database allowlist from JSON file"""
        try:
            data = self._load_allowlist()
            items = data.get("notion_databases", [])
            return [NotionDatabaseAllowlistItem(**item) for item in items]
        except (json.JSONDecodeError, TypeError, KeyError):
            return []

    @property
    def notion_pages(self) -> List[NotionPageAllowlistItem]:
        """Load and return Notion page allowlist from JSON file"""
        try:
            data = self._load_allowlist()
            items = data.get("notion_pages", [])
            return [NotionPageAllowlistItem(**item) for item in items]
        except (json.JSONDecodeError, TypeError, KeyError):
            return []

    # =========================================================================
    # Allowlist Helper Methods
    # =========================================================================

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
