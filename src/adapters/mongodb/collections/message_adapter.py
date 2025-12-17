"""
Message Collection Adapter
"""
from typing import Any, Dict, List, Optional

from ..base import BaseMongoAdapter


class MessageAdapter(BaseMongoAdapter):
    """Adapter for Message collection"""

    collection_name = "Message"

    async def find_one(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find single message document"""
        return await self.col.find_one(filter_dict, projection, session=self.session)

    async def find_many(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
        limit: Optional[int] = None,
        skip: int = 0,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """Find multiple message documents"""
        cursor = self.col.find(filter_dict, projection, session=self.session)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
            return await cursor.to_list(length=limit)
        return await cursor.to_list(length=None)

    async def insert_one(self, document: Dict[str, Any]):
        """Insert message document"""
        return await self.col.insert_one(document, session=self.session)

    async def count_documents(self, filter_dict: Dict[str, Any]) -> int:
        """Count documents matching filter"""
        return await self.col.count_documents(filter_dict, session=self.session)

    async def delete_many(self, filter_dict: Dict[str, Any]):
        """Delete multiple message documents"""
        return await self.col.delete_many(filter_dict, session=self.session)
