"""
SubAgentTrace Collection Adapter

MongoDB adapter for SubAgentTrace collection.
Used for storing sub-agent execution traces for debugging and analysis.
"""
from typing import Any, Dict, List, Optional

from ..base import BaseMongoAdapter


class SubAgentTraceAdapter(BaseMongoAdapter):
    """
    Adapter for SubAgentTrace collection

    Stores detailed trace records of sub-agent executions.
    """

    collection_name = "SubAgentTrace"

    async def find_one(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find single trace document"""
        return await self.col.find_one(filter_dict, projection, session=self.session)

    async def find_many(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
        limit: Optional[int] = None,
        skip: int = 0,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """Find multiple trace documents"""
        cursor = self.col.find(filter_dict, projection, session=self.session)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
            return await cursor.to_list(length=limit)
        return await cursor.to_list(length=None)

    async def insert_one(self, document: Dict[str, Any]):
        """Insert trace document"""
        return await self.col.insert_one(document, session=self.session)

    async def delete_one(self, filter_dict: Dict[str, Any]):
        """Delete single trace document"""
        return await self.col.delete_one(filter_dict, session=self.session)

    async def delete_many(self, filter_dict: Dict[str, Any]):
        """Delete multiple trace documents"""
        return await self.col.delete_many(filter_dict, session=self.session)
