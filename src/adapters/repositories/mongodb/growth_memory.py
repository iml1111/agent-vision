"""MongoDB Growth Memory Repository Implementation"""
from typing import Optional, List
from bson import ObjectId
from loguru import logger
from adapters.mongodb.base import BaseMongoAdapter
from adapters.mongodb.collections.growth_memory_adapter import GrowthMemoryAdapter
from domain.entities.growth_memory import GrowthMemoryEntity
from domain.ports.growth_memory import GrowthMemoryRepository
from domain.value_objects.agent_enums import GrowthMemoryType


class MongoGrowthMemoryRepository(GrowthMemoryRepository):
    """MongoDB implementation of GrowthMemoryRepository with vector search"""

    def __init__(self, adapter: GrowthMemoryAdapter):
        self._adapter = adapter

    async def create(self, entity: GrowthMemoryEntity) -> str:
        """Create new growth memory"""
        doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
        result = await self._adapter.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, memory_id: str) -> Optional[GrowthMemoryEntity]:
        """Retrieve growth memory by ID"""
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

    async def vector_search(
        self,
        query_embedding: List[float],
        limit: int = 10,
        memory_type: Optional[GrowthMemoryType] = None,
        min_score: float = 0.7
    ) -> List[GrowthMemoryEntity]:
        """
        Vector similarity search for relevant memories

        Uses MongoDB Atlas $vectorSearch aggregation.
        """
        filter_dict = None
        if memory_type:
            filter_dict = {"memory_type": memory_type.value}

        docs = await self._adapter.vector_search(
            query_vector=query_embedding,
            limit=limit,
            num_candidates=limit * 10,
            filter_dict=filter_dict
        )

        # Filter by minimum score and convert to entities
        results = []
        for doc in docs:
            score = doc.pop("score", 0)
            if score >= min_score:
                try:
                    entity = GrowthMemoryEntity.from_dict(doc)
                    results.append(entity)
                except (ValueError, KeyError) as e:
                    logger.warning(f"Skipping invalid memory document: {e}")
                    continue

        return results

    async def get_recent(
        self,
        limit: int = 10,
        memory_type: Optional[GrowthMemoryType] = None
    ) -> List[GrowthMemoryEntity]:
        """Get most recent memories"""
        filter_dict = {}
        if memory_type:
            filter_dict["memory_type"] = memory_type.value

        # Exclude embedding from projection for efficiency
        projection = BaseMongoAdapter.entity_projection(GrowthMemoryEntity)

        docs = await self._adapter.find_many(
            filter_dict,
            projection=projection,
            limit=limit,
            sort=[("created_at", -1)]
        )
        return [GrowthMemoryEntity.from_dict(doc) for doc in docs]

    async def get_by_session_id(
        self,
        session_id: str
    ) -> List[GrowthMemoryEntity]:
        """Get memories associated with a session"""
        projection = BaseMongoAdapter.entity_projection(GrowthMemoryEntity)
        docs = await self._adapter.find_many(
            {"source_session_id": session_id},
            projection=projection,
            sort=[("created_at", -1)]
        )
        return [GrowthMemoryEntity.from_dict(doc) for doc in docs]

    async def get_by_tags(
        self,
        tags: List[str],
        limit: int = 10
    ) -> List[GrowthMemoryEntity]:
        """Get memories by tags (OR logic)"""
        projection = BaseMongoAdapter.entity_projection(GrowthMemoryEntity)
        docs = await self._adapter.find_many(
            {"tags": {"$in": tags}},
            projection=projection,
            limit=limit,
            sort=[("created_at", -1)]
        )
        return [GrowthMemoryEntity.from_dict(doc) for doc in docs]

    async def delete(self, memory_id: str) -> bool:
        """Delete a growth memory"""
        try:
            result = await self._adapter.delete_one({"_id": ObjectId(memory_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete memory_id '{memory_id}': {e}")
            return False
