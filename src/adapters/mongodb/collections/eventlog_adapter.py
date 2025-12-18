"""EventLog Collection Adapter"""
from typing import Dict, List, Any, Optional

from motor.motor_asyncio import AsyncIOMotorClientSession

from adapters.mongodb.base import BaseMongoAdapter


class EventLogAdapter(BaseMongoAdapter):
    """
    MongoDB adapter for EventLog collection.

    Provides aggregation capabilities for analytics tools
    (funnel analysis, retention analysis, segment analysis).
    """

    collection_name = "eventlog"

    def __init__(self, db, session: Optional[AsyncIOMotorClientSession] = None):
        """
        Initialize EventLog adapter.

        Args:
            db: MongoDB database instance
            session: Optional session for transactions
        """
        super().__init__(db, session)

    async def aggregate(self, pipeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Execute aggregation pipeline on EventLog collection.

        Args:
            pipeline: MongoDB aggregation pipeline stages

        Returns:
            List of aggregation results
        """
        cursor = self.col.aggregate(pipeline, session=self._session)
        results = await cursor.to_list(length=None)
        return [self.prepare_for_read(doc) for doc in results]
