"""
Observation Collection Adapter
"""
from typing import Optional, Dict, Any, List
from ..base import BaseMongoAdapter


class ObservationAdapter(BaseMongoAdapter):
    """Adapter for Observation collection"""

    collection_name = "Observation"

    async def find_one(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find single observation document"""
        return await self.col.find_one(filter_dict, projection, session=self.session)

    async def find_many(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
        limit: int = 100,
        skip: int = 0,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """Find multiple observation documents"""
        cursor = self.col.find(filter_dict, projection, session=self.session)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def count_documents(self, filter_dict: Dict[str, Any]) -> int:
        """Count documents matching filter"""
        return await self.col.count_documents(filter_dict, session=self.session)

    async def insert_one(self, document: Dict[str, Any]):
        """Insert observation document"""
        return await self.col.insert_one(document, session=self.session)

    async def delete_many(self, filter_dict: Dict[str, Any]):
        """Delete multiple observation documents"""
        return await self.col.delete_many(filter_dict, session=self.session)
