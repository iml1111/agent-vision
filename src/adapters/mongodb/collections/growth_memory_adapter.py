"""
Growth Memory Collection Adapter

Includes vector search support for MongoDB Atlas.
"""
from typing import Optional, Dict, Any, List
from ..base import BaseMongoAdapter


class GrowthMemoryAdapter(BaseMongoAdapter):
    """
    Adapter for GrowthMemory collection

    Includes vector search capabilities using MongoDB Atlas $vectorSearch.
    Requires a vector search index named 'growth_memory_vector_index'.
    """

    collection_name = "GrowthMemory"
    VECTOR_INDEX_NAME = "growth_memory_vector_index"

    async def find_one(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None
    ) -> Optional[Dict[str, Any]]:
        """Find single memory document"""
        return await self.col.find_one(filter_dict, projection, session=self.session)

    async def find_many(
        self,
        filter_dict: Dict[str, Any],
        projection: Optional[Dict[str, int]] = None,
        limit: int = 100,
        skip: int = 0,
        sort: Optional[List[tuple]] = None
    ) -> List[Dict[str, Any]]:
        """Find multiple memory documents"""
        cursor = self.col.find(filter_dict, projection, session=self.session)
        if sort:
            cursor = cursor.sort(sort)
        cursor = cursor.skip(skip).limit(limit)
        return await cursor.to_list(length=limit)

    async def insert_one(self, document: Dict[str, Any]):
        """Insert memory document"""
        return await self.col.insert_one(document, session=self.session)

    async def delete_one(self, filter_dict: Dict[str, Any]):
        """Delete single memory document"""
        return await self.col.delete_one(filter_dict, session=self.session)

    async def vector_search(
        self,
        query_vector: List[float],
        limit: int = 10,
        num_candidates: int = 100,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using MongoDB Atlas $vectorSearch

        Args:
            query_vector: Query embedding vector (1536 dimensions)
            limit: Maximum number of results to return
            num_candidates: Number of candidates to consider (higher = more accurate)
            filter_dict: Optional pre-filter for vector search

        Returns:
            List of documents with similarity scores

        Note:
            Requires MongoDB Atlas with a vector search index configured:
            {
                "name": "growth_memory_vector_index",
                "fields": [
                    {"type": "vector", "path": "embedding", "numDimensions": 1536, "similarity": "cosine"},
                    {"type": "filter", "path": "memory_type"}
                ]
            }
        """
        pipeline = [
            {
                "$vectorSearch": {
                    "index": self.VECTOR_INDEX_NAME,
                    "path": "embedding",
                    "queryVector": query_vector,
                    "numCandidates": num_candidates,
                    "limit": limit
                }
            },
            {
                "$addFields": {
                    "score": {"$meta": "vectorSearchScore"}
                }
            }
        ]

        # Add filter if provided
        if filter_dict:
            pipeline[0]["$vectorSearch"]["filter"] = filter_dict

        cursor = self.col.aggregate(pipeline, session=self.session)
        return await cursor.to_list(length=limit)
