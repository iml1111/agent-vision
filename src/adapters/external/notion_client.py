"""
Notion Client Adapter

Provides Notion API operations for database queries and page content retrieval.
"""
from typing import Optional, Dict, Any, List
from logging_config import get_logger

from adapters.http.client import HTTPClient
from domain.exceptions import NotionAPIError

logger = get_logger(__name__)


class NotionClient(HTTPClient):
    """
    Notion API client

    Extends HTTPClient with Notion-specific operations.
    Uses Integration token authentication.
    """

    BASE_URL = "https://api.notion.com/v1"
    NOTION_VERSION = "2022-06-28"

    def __init__(self, api_key: str, timeout: float = 30.0):
        """
        Initialize Notion client

        Args:
            api_key: Notion Integration API key
            timeout: Request timeout in seconds
        """
        super().__init__(
            base_url=self.BASE_URL,
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Notion-Version": self.NOTION_VERSION
            }
        )

    async def query_database(
        self,
        database_id: str,
        filter_obj: Optional[Dict[str, Any]] = None,
        sorts: Optional[List[Dict[str, Any]]] = None,
        page_size: int = 100,
        start_cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Query a Notion database

        Args:
            database_id: Notion database ID
            filter_obj: Notion filter object
            sorts: List of sort specifications
            page_size: Number of results per page (max 100)
            start_cursor: Pagination cursor

        Returns:
            Dict with results and pagination info

        Raises:
            NotionAPIError: If API call fails
        """
        body: Dict[str, Any] = {
            "page_size": min(page_size, 100)
        }
        if filter_obj:
            body["filter"] = filter_obj
        if sorts:
            body["sorts"] = sorts
        if start_cursor:
            body["start_cursor"] = start_cursor

        try:
            response = await self.post(
                f"databases/{database_id}/query",
                json=body
            )
            return {
                "results": response.get("results", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor")
            }

        except Exception as e:
            logger.error(f"Failed to query database: {e}")
            raise NotionAPIError(f"Failed to query database: {e}") from e

    async def get_database(self, database_id: str) -> Dict[str, Any]:
        """
        Get database metadata

        Args:
            database_id: Notion database ID

        Returns:
            Database metadata dict

        Raises:
            NotionAPIError: If API call fails
        """
        try:
            return await self.get(f"databases/{database_id}")
        except Exception as e:
            logger.error(f"Failed to get database: {e}")
            raise NotionAPIError(f"Failed to get database: {e}") from e

    async def get_page(self, page_id: str) -> Dict[str, Any]:
        """
        Get page metadata and properties

        Args:
            page_id: Notion page ID

        Returns:
            Page metadata dict

        Raises:
            NotionAPIError: If API call fails
        """
        try:
            return await self.get(f"pages/{page_id}")
        except Exception as e:
            logger.error(f"Failed to get page: {e}")
            raise NotionAPIError(f"Failed to get page: {e}") from e

    async def get_page_content(
        self,
        page_id: str,
        page_size: int = 100,
        start_cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get page content blocks

        Args:
            page_id: Notion page ID
            page_size: Number of blocks per page
            start_cursor: Pagination cursor

        Returns:
            Dict with blocks and pagination info

        Raises:
            NotionAPIError: If API call fails
        """
        params = {"page_size": min(page_size, 100)}
        if start_cursor:
            params["start_cursor"] = start_cursor

        try:
            response = await self.get(
                f"blocks/{page_id}/children",
                params=params
            )
            return {
                "blocks": response.get("results", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor")
            }

        except Exception as e:
            logger.error(f"Failed to get page content: {e}")
            raise NotionAPIError(f"Failed to get page content: {e}") from e

    async def search(
        self,
        query: str = "",
        filter_obj: Optional[Dict[str, Any]] = None,
        sort: Optional[Dict[str, str]] = None,
        page_size: int = 100,
        start_cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Search across all pages and databases

        Args:
            query: Search query string
            filter_obj: Filter by object type (page or database)
            sort: Sort specification
            page_size: Number of results per page
            start_cursor: Pagination cursor

        Returns:
            Dict with results and pagination info

        Raises:
            NotionAPIError: If API call fails
        """
        body: Dict[str, Any] = {
            "page_size": min(page_size, 100)
        }
        if query:
            body["query"] = query
        if filter_obj:
            body["filter"] = filter_obj
        if sort:
            body["sort"] = sort
        if start_cursor:
            body["start_cursor"] = start_cursor

        try:
            response = await self.post("search", json=body)
            return {
                "results": response.get("results", []),
                "has_more": response.get("has_more", False),
                "next_cursor": response.get("next_cursor")
            }

        except Exception as e:
            logger.error(f"Failed to search: {e}")
            raise NotionAPIError(f"Failed to search: {e}") from e
