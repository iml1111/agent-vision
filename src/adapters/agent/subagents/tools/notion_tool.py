"""
Notion Tools for Growth Agent

Provides Notion page listing and content retrieval.
"""
from typing import Any, Callable, Dict, List

from logging_config import get_logger
from claude_agent_sdk import tool

from adapters.external.notion_client import NotionClient
from config import Config

logger = get_logger(__name__)


def create_notion_tools(notion_client: NotionClient, config: Config) -> List[Callable[..., Any]]:
    """
    Create Notion tools with injected dependencies.

    Args:
        notion_client: Notion API client
        config: Application config for allowlist access

    Returns:
        List of @tool decorated functions
    """

    @tool(
        "list_notion_pages",
        """List available Notion pages from the allowlist.

Returns a list of allowed pages with:
- page_name: Page title
- page_id: Notion page ID (use with get_notion_page)
- description: Page purpose/description

Use this to discover available pages before calling get_notion_page.""",
        {}
    )
    async def list_notion_pages(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        List Notion pages available in the allowlist.

        Returns:
            List of allowed Notion pages with their IDs and descriptions
        """
        pages = config.notion_pages

        if not pages:
            return {
                "content": [{"type": "text", "text": "No Notion pages configured in allowlist"}]
            }

        response_text = "Available Notion Pages:\n"
        for page in pages:
            desc = f" - {page.description}" if page.description else ""
            response_text += f"- {page.page_name} (ID: {page.page_id}){desc}\n"

        return {
            "content": [{"type": "text", "text": response_text}]
        }

    @tool(
        "get_notion_page",
        """Get content from a Notion page.

## Parameters
- page_id (required): Notion page ID from list_notion_pages

## Response Format
Returns the page content as formatted text:
- Headings (#, ##, ###)
- Paragraphs
- Bullet/numbered lists
- Code blocks with language
- Quotes and callouts

Note: Page properties are not included, only the main content body.""",
        {
            "page_id": str
        }
    )
    async def get_notion_page(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get properties and content from a Notion page.

        Args:
            page_id: Notion page ID

        Returns:
            Page properties and content as text
        """
        page_id = args.get("page_id")

        try:
            # Get page metadata and properties
            page = await notion_client.get_page(page_id)
            properties = page.get("properties", {})

            # Get page content blocks
            content_result = await notion_client.get_page_content(page_id)
            blocks = content_result.get("blocks", [])

            # Get page name from allowlist or properties
            page_info = config.get_notion_page_info(page_id)
            page_name = page_info.page_name if page_info else _extract_title(properties)

            # Build response
            response_text = f"Page: {page_name}\n"
            response_text += f"ID: {page_id}\n"
            response_text += "-" * 40 + "\n\n"

            # Add properties section
            if properties:
                response_text += "## Properties\n"
                for prop_name, prop_value in properties.items():
                    prop_text = _format_property(prop_value)
                    if prop_text:
                        response_text += f"- {prop_name}: {prop_text}\n"
                response_text += "\n"

            # Add content section
            response_text += "## Content\n"
            for block in blocks:
                block_text = _format_block(block)
                if block_text:
                    response_text += block_text

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

    @tool(
        "get_eventlog_specs",
        """Get EventLog specification definitions from Notion DB.

Returns all event definitions with:
- 이름: Event name/type (e.g., "login_success", "complete_purchase")
- Description: Event description and purpose
- Extra Fields: Additional fields in the extra object for this event

Use this to understand available events before running aggregation queries.

## Example Response
1. login_success
   Description: 로그인 성공 시 발생
   Extra Fields: email, login_method

2. complete_purchase
   Description: 결제 완료 시 발생
   Extra Fields: order_id, total_amount, credit_count""",
        {}
    )
    async def get_eventlog_specs(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Query the EventLog spec definition database.

        Returns:
            List of event specifications with name, description, and extra fields
        """
        db_id = config.notion_eventlog_spec_db_id

        if not db_id:
            return {
                "content": [{"type": "text", "text": "EventLog spec database ID not configured"}],
                "is_error": True
            }

        try:
            # Fetch all events with pagination
            all_results = []
            start_cursor = None

            while True:
                result = await notion_client.query_database(
                    database_id=db_id,
                    page_size=100,
                    start_cursor=start_cursor
                )

                all_results.extend(result.get("results", []))

                if not result.get("has_more"):
                    break

                start_cursor = result.get("next_cursor")

            if not all_results:
                return {
                    "content": [{"type": "text", "text": "No event specifications found"}]
                }

            response_text = f"EventLog Specifications ({len(all_results)} events):\n"
            response_text += "=" * 40 + "\n\n"

            for i, item in enumerate(all_results, 1):
                properties = item.get("properties", {})

                # Extract event name (Title)
                event_name = _format_property(properties.get("이름", {}))

                # Extract description (rich_text)
                description = _format_property(properties.get("Description", {}))

                # Extract extra fields (rich_text)
                extra_fields = _format_property(properties.get("Extra Fields", {}))

                response_text += f"{i}. {event_name or 'Unnamed Event'}\n"
                if description:
                    response_text += f"   Description: {description}\n"
                if extra_fields:
                    response_text += f"   Extra Fields: {extra_fields}\n"
                response_text += "\n"

            return {
                "content": [{"type": "text", "text": response_text}]
            }

        except Exception as e:
            logger.error(f"Failed to get EventLog specs: {e}")
            return {
                "content": [{"type": "text", "text": f"Error retrieving EventLog specs: {str(e)}"}],
                "is_error": True
            }

    return [list_notion_pages, get_notion_page, get_eventlog_specs]


def _extract_title(properties: Dict[str, Any]) -> str:
    """Extract title from properties"""
    for prop_value in properties.values():
        if prop_value.get("type") == "title":
            title_content = prop_value.get("title", [])
            if title_content:
                return title_content[0].get("plain_text", "Untitled")
    return "Untitled"


def _format_property(prop_value: Dict[str, Any]) -> str:
    """Format a single property value to string"""
    prop_type = prop_value.get("type", "")

    if prop_type == "title":
        title_content = prop_value.get("title", [])
        return "".join([t.get("plain_text", "") for t in title_content])

    elif prop_type == "rich_text":
        rich_text = prop_value.get("rich_text", [])
        return "".join([t.get("plain_text", "") for t in rich_text])

    elif prop_type == "number":
        return str(prop_value.get("number", ""))

    elif prop_type == "select":
        select = prop_value.get("select")
        return select.get("name", "") if select else ""

    elif prop_type == "multi_select":
        multi = prop_value.get("multi_select", [])
        return ", ".join([m.get("name", "") for m in multi])

    elif prop_type == "date":
        date = prop_value.get("date")
        if date:
            start = date.get("start", "")
            end = date.get("end")
            return f"{start} ~ {end}" if end else start
        return ""

    elif prop_type == "checkbox":
        return "Yes" if prop_value.get("checkbox") else "No"

    elif prop_type == "url":
        return prop_value.get("url", "")

    elif prop_type == "email":
        return prop_value.get("email", "")

    elif prop_type == "phone_number":
        return prop_value.get("phone_number", "")

    elif prop_type == "status":
        status = prop_value.get("status")
        return status.get("name", "") if status else ""

    return ""


def _format_block(block: Dict[str, Any]) -> str:
    """Format a single block to string"""
    block_type = block.get("type", "")
    block_content = block.get(block_type, {})

    if block_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item"]:
        rich_text = block_content.get("rich_text", [])
        text = "".join([t.get("plain_text", "") for t in rich_text])

        if not text:
            return ""

        if block_type.startswith("heading"):
            level = block_type[-1]
            return f"{'#' * int(level)} {text}\n\n"
        elif block_type in ["bulleted_list_item", "numbered_list_item"]:
            return f"- {text}\n"
        else:
            return f"{text}\n\n"

    elif block_type == "code":
        rich_text = block_content.get("rich_text", [])
        code = "".join([t.get("plain_text", "") for t in rich_text])
        language = block_content.get("language", "")
        return f"```{language}\n{code}\n```\n\n"

    elif block_type == "quote":
        rich_text = block_content.get("rich_text", [])
        text = "".join([t.get("plain_text", "") for t in rich_text])
        return f"> {text}\n\n"

    elif block_type == "divider":
        return "---\n\n"

    elif block_type == "callout":
        rich_text = block_content.get("rich_text", [])
        text = "".join([t.get("plain_text", "") for t in rich_text])
        icon = block_content.get("icon", {}).get("emoji", "💡")
        return f"{icon} {text}\n\n"

    elif block_type == "table":
        return _format_table(block)

    return ""


def _format_table(block: Dict[str, Any]) -> str:
    """Format table block to markdown table"""
    table_info = block.get("table", {})
    rows = block.get("table_rows", [])

    if not rows:
        return "[Empty table]\n\n"

    table_width = table_info.get("table_width", 0)
    has_header = table_info.get("has_column_header", False)

    result = ""
    for idx, row in enumerate(rows):
        cells = row.get("table_row", {}).get("cells", [])
        values = []
        for cell in cells:
            cell_text = "".join([t.get("plain_text", "") for t in cell])
            # Escape pipe characters in cell content
            cell_text = cell_text.replace("|", "\\|")
            values.append(cell_text)

        result += "| " + " | ".join(values) + " |\n"

        # Add separator after header row
        if idx == 0:
            if has_header:
                result += "|" + "|".join(["---"] * table_width) + "|\n"
            else:
                # No header, add separator after first row anyway for valid markdown
                result += "|" + "|".join(["---"] * table_width) + "|\n"

    return result + "\n"
