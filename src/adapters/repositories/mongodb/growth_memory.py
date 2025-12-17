"""MongoDB GrowthMemory Repository Implementation"""
from typing import List, Optional

from bson import ObjectId
from loguru import logger

from adapters.mongodb.base import BaseMongoAdapter
from adapters.mongodb.collections.growth_memory_adapter import GrowthMemoryAdapter
from domain.entities.growth_memory import GrowthMemoryEntity
from domain.ports.growth_memory import GrowthMemoryRepository


class MongoGrowthMemoryRepository(GrowthMemoryRepository):
    """MongoDB implementation of GrowthMemoryRepository"""

    def __init__(self, adapter: GrowthMemoryAdapter):
        self._adapter = adapter

    async def create(self, entity: GrowthMemoryEntity) -> str:
        """Create new growth memory document"""
        doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
        result = await self._adapter.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, memory_id: str) -> Optional[GrowthMemoryEntity]:
        """Retrieve memory by ID"""
        projection = BaseMongoAdapter.entity_projection(GrowthMemoryEntity)
        try:
            doc = await self._adapter.find_one({"_id": ObjectId(memory_id)}, projection)
        except Exception as e:
            logger.error(f"Invalid memory_id format '{memory_id}': {e}")
            return None

        if not doc:
            return None

        try:
            return GrowthMemoryEntity.from_dict(doc)
        except (ValueError, KeyError) as e:
            logger.error(f"Data validation failed for memory_id '{memory_id}': {e}")
            raise

    async def get_by_session_id(self, session_id: str) -> Optional[GrowthMemoryEntity]:
        """Retrieve memory by original session ID"""
        projection = BaseMongoAdapter.entity_projection(GrowthMemoryEntity)
        doc = await self._adapter.find_one({"session_id": session_id}, projection)

        if not doc:
            return None

        try:
            return GrowthMemoryEntity.from_dict(doc)
        except (ValueError, KeyError) as e:
            logger.error(f"Data validation failed for session_id '{session_id}': {e}")
            raise

    async def vector_search(
        self,
        query_vector: List[float],
        limit: int = 5,
        min_score: float = 0.7
    ) -> List[GrowthMemoryEntity]:
        """
        Search memories by vector similarity

        Uses Atlas Vector Search on content_vector field.

        Args:
            query_vector: Query embedding vector (1536 dimensions)
            limit: Maximum number of results
            min_score: Minimum similarity score threshold

        Returns:
            List of GrowthMemoryEntity ordered by similarity
        """
        docs = await self._adapter.vector_search(query_vector, limit, min_score)

        results = []
        for doc in docs:
            try:
                # Remove search_score before converting to entity
                doc.pop("search_score", None)
                entity = GrowthMemoryEntity.from_dict(doc)
                results.append(entity)
            except (ValueError, KeyError) as e:
                logger.error(f"Data validation failed during vector search: {e}")
                continue

        return results

    async def delete(self, memory_id: str) -> bool:
        """Delete memory document"""
        try:
            result = await self._adapter.delete_one({"_id": ObjectId(memory_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete memory_id '{memory_id}': {e}")
            return False

    async def delete_by_session_id(self, session_id: str) -> bool:
        """Delete memory by original session ID"""
        result = await self._adapter.delete_one({"session_id": session_id})
        return result.deleted_count > 0
