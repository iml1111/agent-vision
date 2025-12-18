"""
EventLog Tools for Growth Agent

Provides funnel analysis, retention analysis, and segment analysis
using MongoDB aggregation pipelines on the EventLog collection.
"""
from typing import Any, Callable, Dict, List, Optional
from datetime import datetime
from logging_config import get_logger

from claude_code_sdk import tool

from adapters.mongodb.collections.eventlog_adapter import EventLogAdapter

logger = get_logger(__name__)


def create_eventlog_tools(eventlog_adapter: EventLogAdapter) -> List[Callable[..., Any]]:
    """
    Create EventLog tools with injected adapter.

    Args:
        eventlog_adapter: EventLog collection adapter for MongoDB operations

    Returns:
        List of @tool decorated functions
    """

    @tool(
        "funnel_analysis",
        "Analyze user funnel conversion rates between sequential events",
        {
            "events": List[str],
            "start_date": str,
            "end_date": str,
            "filters": Optional[Dict[str, Any]]
        }
    )
    async def funnel_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze funnel conversion between sequential events.

        Args:
            events: List of event names in sequence (e.g., ["page_view", "add_to_cart", "purchase"])
            start_date: Start date in ISO format
            end_date: End date in ISO format
            filters: Optional filters (e.g., {"platform": "ios"})

        Returns:
            Funnel analysis with conversion rates at each step
        """
        events_list = args.get("events", [])
        start_date = args.get("start_date")
        end_date = args.get("end_date")
        filters = args.get("filters", {})

        if len(events_list) < 2:
            return {
                "content": [{"type": "text", "text": "At least 2 events required for funnel analysis"}],
                "is_error": True
            }

        try:
            match_stage = {
                "$match": {
                    "event_name": {"$in": events_list},
                    "timestamp": {
                        "$gte": datetime.fromisoformat(start_date),
                        "$lte": datetime.fromisoformat(end_date)
                    },
                    **filters
                }
            }

            group_stage = {
                "$group": {
                    "_id": "$user_id",
                    "events": {"$addToSet": "$event_name"}
                }
            }

            pipeline = [match_stage, group_stage]
            results = await eventlog_adapter.aggregate(pipeline)

            funnel_results = []
            total_users = len(results)

            for i, event in enumerate(events_list):
                users_at_step = sum(1 for r in results if event in r.get("events", []))
                conversion_rate = (users_at_step / total_users * 100) if total_users > 0 else 0
                drop_off = 0
                if i > 0 and len(funnel_results) > 0:
                    prev_users = funnel_results[i-1]["users"]
                    drop_off = ((prev_users - users_at_step) / prev_users * 100) if prev_users > 0 else 0

                funnel_results.append({
                    "step": i + 1,
                    "event": event,
                    "users": users_at_step,
                    "conversion_rate": round(conversion_rate, 2),
                    "drop_off_rate": round(drop_off, 2)
                })

            response_text = f"Funnel Analysis ({start_date} to {end_date}):\n"
            for step in funnel_results:
                response_text += f"Step {step['step']} ({step['event']}): {step['users']} users ({step['conversion_rate']}% conversion, {step['drop_off_rate']}% drop-off)\n"

            return {
                "content": [{"type": "text", "text": response_text}]
            }

        except Exception as e:
            logger.error(f"Funnel analysis failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Funnel analysis error: {str(e)}"}],
                "is_error": True
            }

    @tool(
        "retention_analysis",
        "Analyze user retention over time periods",
        {
            "cohort_event": str,
            "return_event": str,
            "start_date": str,
            "end_date": str,
            "periods": int,
            "period_unit": str
        }
    )
    async def retention_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze user retention for cohorts.

        Args:
            cohort_event: Event that defines cohort entry (e.g., "signup")
            return_event: Event that defines return (e.g., "login")
            start_date: Cohort start date in ISO format
            end_date: Cohort end date in ISO format
            periods: Number of periods to track (e.g., 7 for 7 days)
            period_unit: "day", "week", or "month"

        Returns:
            Retention analysis with retention rates per period
        """
        try:
            cohort_event = args.get("cohort_event")
            return_event = args.get("return_event")
            start_date = args.get("start_date")
            end_date = args.get("end_date")

            pipeline = [
                {
                    "$match": {
                        "event_name": {"$in": [cohort_event, return_event]},
                        "timestamp": {
                            "$gte": datetime.fromisoformat(start_date),
                            "$lte": datetime.fromisoformat(end_date)
                        }
                    }
                },
                {
                    "$group": {
                        "_id": "$user_id",
                        "first_cohort_event": {"$min": {"$cond": [{"$eq": ["$event_name", cohort_event]}, "$timestamp", None]}},
                        "return_events": {"$push": {"$cond": [{"$eq": ["$event_name", return_event]}, "$timestamp", None]}}
                    }
                }
            ]

            results = await eventlog_adapter.aggregate(pipeline)

            total_cohort = len([r for r in results if r.get("first_cohort_event")])

            response_text = f"Retention Analysis for {cohort_event} -> {return_event}:\n"
            response_text += f"Cohort size: {total_cohort} users\n"
            response_text += f"Period: {start_date} to {end_date}\n"
            response_text += f"Note: Detailed period-by-period retention requires additional processing\n"

            return {
                "content": [{"type": "text", "text": response_text}]
            }

        except Exception as e:
            logger.error(f"Retention analysis failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Retention analysis error: {str(e)}"}],
                "is_error": True
            }

    @tool(
        "segment_analysis",
        "Analyze user segments based on event properties",
        {
            "event_name": str,
            "segment_by": str,
            "start_date": str,
            "end_date": str,
            "metric": str
        }
    )
    async def segment_analysis(args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze user segments based on event properties.

        Args:
            event_name: Event to analyze
            segment_by: Property to segment by (e.g., "platform", "country")
            start_date: Start date in ISO format
            end_date: End date in ISO format
            metric: "count" or "unique_users"

        Returns:
            Segment breakdown with counts
        """
        try:
            event_name = args.get("event_name")
            segment_by = args.get("segment_by")
            start_date = args.get("start_date")
            end_date = args.get("end_date")
            metric = args.get("metric", "count")

            pipeline = [
                {
                    "$match": {
                        "event_name": event_name,
                        "timestamp": {
                            "$gte": datetime.fromisoformat(start_date),
                            "$lte": datetime.fromisoformat(end_date)
                        }
                    }
                },
                {
                    "$group": {
                        "_id": f"$properties.{segment_by}",
                        "count": {"$sum": 1},
                        "unique_users": {"$addToSet": "$user_id"}
                    }
                },
                {
                    "$project": {
                        "segment": "$_id",
                        "count": 1,
                        "unique_users": {"$size": "$unique_users"}
                    }
                },
                {"$sort": {"count": -1}}
            ]

            results = await eventlog_adapter.aggregate(pipeline)

            response_text = f"Segment Analysis for {event_name} by {segment_by}:\n"
            response_text += f"Period: {start_date} to {end_date}\n\n"

            for segment in results[:20]:
                value = metric if metric == "count" else "unique_users"
                response_text += f"- {segment.get('segment', 'Unknown')}: {segment.get(value, 0)}\n"

            return {
                "content": [{"type": "text", "text": response_text}]
            }

        except Exception as e:
            logger.error(f"Segment analysis failed: {e}")
            return {
                "content": [{"type": "text", "text": f"Segment analysis error: {str(e)}"}],
                "is_error": True
            }

    return [funnel_analysis, retention_analysis, segment_analysis]
