"""External Integration Adapters"""
from .slack_client import SlackClient
from .notion_client import NotionClient

__all__ = ["SlackClient", "NotionClient"]
