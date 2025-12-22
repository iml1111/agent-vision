"""
EventLog Tool for Growth Agent

Provides raw MongoDB aggregation pipeline execution on the EventLog collection
with validation and security constraints.
"""
import json
from typing import Any, Callable, Dict, List, Set

from logging_config import get_logger
from claude_agent_sdk import tool

from adapters.mongodb.collections.eventlog_adapter import EventLogAdapter

logger = get_logger(__name__)

# Whitelist of allowed aggregation stages (21 stages)
ALLOWED_STAGES: Set[str] = {
    # Filtering
    "$match",
    # Projection
    "$project", "$addFields", "$set", "$unset", "$unwind",
    # Grouping & Aggregation
    "$group", "$count", "$sortByCount", "$bucket", "$bucketAuto",
    # Sorting & Pagination
    "$sort", "$limit", "$skip",
    # Conditional
    "$replaceRoot", "$replaceWith",
    # Advanced
    "$facet", "$setWindowFields", "$densify", "$fill",
    # Date
    "$dateTrunc",
    # Note: $lookup is intentionally excluded to prevent cross-collection join attempts
}

# Blocked stages for security
BLOCKED_STAGES: Set[str] = {"$out", "$merge", "$where", "$function"}

def _validate_pipeline(pipeline: List[Dict[str, Any]]) -> tuple[bool, str]:
    """
    Validate aggregation pipeline against security constraints.

    Returns:
        (is_valid, error_message)
    """
    if not pipeline:
        return False, "Pipeline cannot be empty"

    if not isinstance(pipeline, list):
        return False, "Pipeline must be a list of stages"

    has_limit = False

    for i, stage in enumerate(pipeline):
        if not isinstance(stage, dict):
            return False, f"Stage {i} must be a dictionary"

        if len(stage) != 1:
            return False, f"Stage {i} must have exactly one operator"

        operator = list(stage.keys())[0]

        # Check blocked stages
        if operator in BLOCKED_STAGES:
            return False, f"Stage '{operator}' is not allowed (security restriction)"

        # Check allowed stages
        if operator not in ALLOWED_STAGES:
            return False, f"Stage '{operator}' is not in the allowed stages list"

        # Check $limit presence
        if operator == "$limit":
            has_limit = True

    # Enforce $limit requirement
    if not has_limit:
        return False, "$limit stage is required in every pipeline"

    return True, ""


# Tool description with full schema documentation
RUN_EVENTLOG_AGGREGATION_DESCRIPTION = """Execute MongoDB aggregation pipeline on EventLog collection.

## EventLog Document Schema

### Core Fields (Always Available)
- event: string - Event type (e.g., "login_success", "page_view", "complete_purchase")
- timestamp: datetime (UTC) - When the event occurred
- session_id: string - Session identifier
- platform: enum - Platform identifier
  * Values: api, pc_web, mobile_web, ios, android, ipad, mac_app, windows_app, chrome_extension, safari_extension, smart_tv, kiosk, wearable
- version: string - App/service version

### Optional Fields
- user_id: string - User identifier (logged-in users only)
- stage: string - Deployment environment (dev, staging, prod)
- utm_source: string - UTM source (e.g., "ig", "google", "facebook")
- utm_campaign: string - UTM campaign (e.g., "Leslie_251023")

### Dynamic Field
- extra: object - Additional event-specific data
  * Common fields: email, utm_medium, referrer_url
  * Page view events: path, page_title
  * Click events: button_id
  * Scroll events: (no additional fields beyond common)
  * Notification events: notification_id, notification_type
  * Mock interview events: mode
  * Purchase events: order_id, total_amount, credit_count
  * Different extra fields for each event type (see Event Specs)

### Example Document (page_view_intro)
```json
{
  "_id": "6947f5a798ee9039846229f9",
  "event": "page_view_intro",
  "timestamp": "2025-12-21T13:27:03.726Z",
  "session_id": "d07056f8-1c46-49c9-aba4-a52409957a09",
  "platform": "mobile_web",
  "version": "1.0.5",
  "user_id": null,
  "stage": "prod",
  "utm_source": "ig",
  "utm_campaign": "Leslie_251023",
  "extra": {
    "email": null,
    "utm_medium": "Instagram_Reels",
    "referrer_url": "https://leslieai.io/?utm_source=ig&...",
    "path": "/",
    "page_title": "Leslie AI | AI Career Mentor for Jobs and Transitions"
  }
}
```

## Allowed Aggregation Stages (21 stages)
- Filtering: $match
- Projection: $project, $addFields, $set, $unset, $unwind
- Grouping: $group, $count, $sortByCount, $bucket, $bucketAuto
- Sorting/Pagination: $sort, $limit (REQUIRED), $skip
- Conditional: $replaceRoot, $replaceWith
- Advanced: $facet, $setWindowFields, $densify, $fill
- Date: $dateTrunc

## NOT ALLOWED (Security)
- $out, $merge (write operations)
- $where, $function (server-side JavaScript)
- $lookup (joins not supported)

## IMPORTANT
- $limit stage is MANDATORY in every pipeline
- All dates should be ISO format strings or Date objects"""


def create_eventlog_tools(eventlog_adapter: EventLogAdapter) -> List[Callable[..., Any]]:
    """
    Create EventLog tools with injected adapter.

    Args:
        eventlog_adapter: EventLog collection adapter for MongoDB operations

    Returns:
        List of @tool decorated functions
    """

    @tool(
        "run_eventlog_aggregation",
        RUN_EVENTLOG_AGGREGATION_DESCRIPTION,
        {
            "pipeline": List[Dict[str, Any]],
        }
    )
    async def run_eventlog_aggregation(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute MongoDB aggregation pipeline on EventLog collection.

        Args:
            pipeline: MongoDB aggregation pipeline stages

        Returns:
            Aggregation results or error
        """
        pipeline = args.get("pipeline", [])

        # Handle string input (LLM sometimes sends JSON string)
        if isinstance(pipeline, str):
            try:
                pipeline = json.loads(pipeline)
            except json.JSONDecodeError:
                logger.warning("Pipeline is invalid JSON string")
                return {
                    "content": [{"type": "text", "text": "Pipeline validation error: Invalid JSON string"}],
                    "is_error": True
                }

        # Validate pipeline
        is_valid, error_msg = _validate_pipeline(pipeline)
        if not is_valid:
            logger.warning(f"Pipeline validation failed: {error_msg}")
            return {
                "content": [{"type": "text", "text": f"Pipeline validation error: {error_msg}"}],
                "is_error": True
            }

        try:
            results = await eventlog_adapter.aggregate(pipeline)

            # Format results
            result_count = len(results)
            result_text = f"Aggregation completed. {result_count} document(s) returned.\n\n"

            if result_count > 0:
                result_text += json.dumps(results, indent=2, default=str, ensure_ascii=False)

            return {
                "content": [{"type": "text", "text": result_text}]
            }

        except Exception as e:
            logger.error(f"EventLog aggregation failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Aggregation error: {str(e)}"}],
                "is_error": True
            }

    return [run_eventlog_aggregation]
