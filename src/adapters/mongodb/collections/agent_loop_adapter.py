"""
Agent Loop Collection Adapter
"""
from typing import Optional, Dict, Any, List
from ..base import BaseMongoAdapter


class AgentLoopAdapter(BaseMongoAdapter):
    """Adapter for AgentLoop collection"""

    collection_name = "AgentLoop"

    async def find_one(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find single loop document"""
        return await self.col.find_one(filter_dict, projection, session=self.session)

    async def find_many(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
        limit: int = 100,
        skip: int = 0,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """Find multiple loop documents"""
        cursor = self.col.find(filter_dict, projection, session=self.session)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def insert_one(self, document: Dict[str, Any]):
        """Insert loop document"""
        return await self.col.insert_one(document, session=self.session)

    async def update_one(
        self,
        filter_dict: Dict[str, Any],
        update: Dict[str, Any]
    ):
        """Update single loop document"""
        return await self.col.update_one(filter_dict, update, session=self.session)

    async def delete_one(self, filter_dict: Dict[str, Any]):
        """Delete single loop document"""
        return await self.col.delete_one(filter_dict, session=self.session)
