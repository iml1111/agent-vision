"""
GrowthMemory Collection Adapter

MongoDB adapter for GrowthMemory collection with Atlas Vector Search support.
"""
from typing import Any, Dict, List, Optional

from ..base import BaseMongoAdapter


class GrowthMemoryAdapter(BaseMongoAdapter):
    """
    Adapter for GrowthMemory collection

    Supports Atlas Vector Search on content_vector field.
    """

    collection_name = "GrowthMemory"
    VECTOR_INDEX_NAME = "growth_memory_vector_index"

    async def find_one(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find single growth memory document"""
        return await self.col.find_one(filter_dict, projection, session=self.session)

    async def find_many(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
        limit: Optional[int] = None,
        skip: int = 0,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """Find multiple growth memory documents"""
        cursor = self.col.find(filter_dict, projection, session=self.session)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip)
        if limit:
            cursor = cursor.limit(limit)
            return await cursor.to_list(length=limit)
        return await cursor.to_list(length=None)

    async def insert_one(self, document: Dict[str, Any]):
        """Insert growth memory document"""
        return await self.col.insert_one(document, session=self.session)

    async def delete_one(self, filter_dict: Dict[str, Any]):
        """Delete single growth memory document"""
        return await self.col.delete_one(filter_dict, session=self.session)

    async def vector_search(
        self,
        query_vector: List[float],
        limit: int = 5,
        min_score: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Perform Atlas Vector Search on content_vector field.

        Uses $vectorSearch aggregation pipeline for semantic similarity search.

        Args:
            query_vector: Query embedding vector (1536 dimensions)
            limit: Maximum number of results
            min_score: Minimum similarity score threshold

        Returns:
            List of documents with search_score field added
        """
        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.VECTOR_INDEX_NAME,
                    "path": "content_vector",
                    "queryVector": query_vector,
                    "numCandidates": limit * 10,
                    "limit": limit
                }
            },
            {
                "$addFields": {
                    "search_score": {"$meta": "vectorSearchScore"}
                }
            },
            {
                "$match": {
                    "search_score": {"$gte": min_score}
                }
            }
        ]

        cursor = self.col.aggregate(pipeline)
        return await cursor.to_list(length=limit)
