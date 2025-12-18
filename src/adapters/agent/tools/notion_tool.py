"""
Notion Tools for Growth Agent

Provides Notion database querying and page content retrieval
with allowlist enforcement.
"""
from typing import Any, Dict, List, Optional
from logging_config import get_logger

from claude_code_sdk import tool

logger = get_logger(__name__)


# Module-level dependencies (set during app initialization)
_notion_client = None
_config = None


def set_notion_dependencies(notion_client, config):
    """Set Notion client and config for tool use"""
    global _notion_client, _config
    _notion_client = notion_client
    _config = config


@tool(
    "list_notion_resources",
    "List available Notion databases and pages from the allowlist",
    {}
)
async def list_notion_resources(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    List Notion resources available in the allowlist.

    Returns:
        List of allowed Notion databases and pages
    """
    if _config is None:
        return {
            "content": [{"type": "text", "text": "Config not initialized"}],
            "is_error": True
        }

    try:
        databases = _config.notion_databases
        pages = _config.notion_pages

        response_text = "Available Notion Resources:\n\n"

        if databases:
            response_text += "Databases:\n"
            for db in databases:
                desc = f" - {db.description}" if db.description else ""
                response_text += f"- {db.database_name} (ID: {db.database_id}){desc}\n"
        else:
            response_text += "Databases: None configured\n"

        response_text += "\n"

        if pages:
            response_text += "Pages:\n"
            for page in pages:
                desc = f" - {page.description}" if page.description else ""
                response_text += f"- {page.page_name} (ID: {page.page_id}){desc}\n"
        else:
            response_text += "Pages: None configured\n"

        return {
            "content": [{"type": "text", "text": response_text}]
        }

    except Exception as e:
        logger.error(f"Failed to list Notion resources: {e}")
        return {
            "content": [{"type": "text", "text": f"Error listing resources: {str(e)}"}],
            "is_error": True
        }


@tool(
    "query_notion_database",
    "Query a Notion database (must be in allowlist)",
    {
        "database_id": str,
        "filter": Optional[Dict[str, Any]],
        "sorts": Optional[List[Dict[str, Any]]],
        "page_size": int
    }
)
async def query_notion_database(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Query a Notion database.

    Args:
        database_id: Notion database ID (must be in allowlist)
        filter: Optional Notion filter object
        sorts: Optional list of sort specifications
        page_size: Number of results to return (default 50, max 100)

    Returns:
        Query results from the database
    """
    if _notion_client is None or _config is None:
        return {
            "content": [{"type": "text", "text": "Notion dependencies not initialized"}],
            "is_error": True
        }

    database_id = args.get("database_id")
    filter_obj = args.get("filter")
    sorts = args.get("sorts")
    page_size = min(args.get("page_size", 50), 100)

    # Allowlist check (server-side enforcement)
    if not _config.is_notion_database_allowed(database_id):
        return {
            "content": [{"type": "text", "text": f"Access denied: Database {database_id} is not in the allowlist"}],
            "is_error": True
        }

    try:
        result = await _notion_client.query_database(
            database_id=database_id,
            filter_obj=filter_obj,
            sorts=sorts,
            page_size=page_size
        )

        results = result.get("results", [])

        if not results:
            return {
                "content": [{"type": "text", "text": "No results found"}]
            }

        # Format results for response
        db_info = _config.get_notion_database_info(database_id)
        db_name = db_info.database_name if db_info else database_id

        response_text = f"Query Results from {db_name} ({len(results)} items):\n\n"

        for item in results[:page_size]:
            page_id = item.get("id", "unknown")
            properties = item.get("properties", {})

            # Extract title if present
            title = "Untitled"
            for prop_name, prop_value in properties.items():
                if prop_value.get("type") == "title":
                    title_content = prop_value.get("title", [])
                    if title_content:
                        title = title_content[0].get("plain_text", "Untitled")
                    break

            response_text += f"- {title} (ID: {page_id})\n"

        if result.get("has_more"):
            response_text += "\n(More results available - use pagination to retrieve)"

        return {
            "content": [{"type": "text", "text": response_text}]
        }

    except Exception as e:
        logger.error(f"Failed to query Notion database: {e}")
        return {
            "content": [{"type": "text", "text": f"Error querying database: {str(e)}"}],
            "is_error": True
        }


@tool(
    "get_notion_page",
    "Get content from a Notion page (must be in allowlist)",
    {
        "page_id": str
    }
)
async def get_notion_page(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get content from a Notion page.

    Args:
        page_id: Notion page ID (must be in allowlist)

    Returns:
        Page content as text
    """
    if _notion_client is None or _config is None:
        return {
            "content": [{"type": "text", "text": "Notion dependencies not initialized"}],
            "is_error": True
        }

    page_id = args.get("page_id")

    # Allowlist check (server-side enforcement)
    if not _config.is_notion_page_allowed(page_id):
        return {
            "content": [{"type": "text", "text": f"Access denied: Page {page_id} is not in the allowlist"}],
            "is_error": True
        }

    try:
        # Get page metadata
        page = await _notion_client.get_page(page_id)

        # Get page content blocks
        content_result = await _notion_client.get_page_content(page_id)
        blocks = content_result.get("blocks", [])

        # Format page info
        page_info = _config.get_notion_page_info(page_id)
        page_name = page_info.page_name if page_info else page_id

        response_text = f"Page: {page_name}\n"
        response_text += f"ID: {page_id}\n"
        response_text += "-" * 40 + "\n\n"

        # Extract text content from blocks
        for block in blocks:
            block_type = block.get("type", "")
            block_content = block.get(block_type, {})

            if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
                rich_text = block_content.get("rich_text", [])
                text = "".join([t.get("plain_text", "") for t in rich_text])

                if block_type.startswith("heading"):
                    level = block_type[-1]
                    response_text += f"{'#' * int(level)} {text}\n\n"
                elif block_type in ["bulleted_list_item", "numbered_list_item"]:
                    response_text += f"- {text}\n"
                else:
                    response_text += f"{text}\n\n"

        if content_result.get("has_more"):
            response_text += "\n(Page has more content - use pagination to retrieve)"

        return {
            "content": [{"type": "text", "text": response_text}]
        }

    except Exception as e:
        logger.error(f"Failed to get Notion page: {e}")
        return {
            "content": [{"type": "text", "text": f"Error retrieving page: {str(e)}"}],
            "is_error": True
        }
