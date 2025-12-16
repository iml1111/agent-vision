"""MongoDB Observation Repository Implementation"""
from typing import Optional, List
from bson import ObjectId
from loguru import logger
from adapters.mongodb.base import BaseMongoAdapter
from adapters.mongodb.collections.observation_adapter import ObservationAdapter
from domain.entities.observation import ObservationEntity
from domain.ports.observation import ObservationRepository
from domain.value_objects.agent_enums import ObservationType


class MongoObservationRepository(ObservationRepository):
    """MongoDB implementation of ObservationRepository"""

    def __init__(self, adapter: ObservationAdapter):
        self._adapter = adapter

    async def create(self, entity: ObservationEntity) -> str:
        """Create new observation"""
        doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
        result = await self._adapter.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, observation_id: str) -> Optional[ObservationEntity]:
        """Retrieve observation by ID"""
        projection = BaseMongoAdapter.entity_projection(ObservationEntity)
        try:
            doc = await self._adapter.find_one({"_id": ObjectId(observation_id)}, projection)
        except Exception as e:
            logger.error(f"Invalid observation_id format '{observation_id}': {e}")
            return None

        if not doc:
            return None

        try:
            return ObservationEntity.from_dict(doc)
        except (ValueError, KeyError) as e:
            logger.error(f"Data validation failed for observation_id '{observation_id}': {e}")
            raise

    async def get_by_session_id(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[ObservationEntity]:
        """Get observations for a session"""
        projection = BaseMongoAdapter.entity_projection(ObservationEntity)
        docs = await self._adapter.find_many(
            {"session_id": session_id},
            projection=projection,
            limit=limit,
            skip=offset,
            sort=[("created_at", -1)]
        )
        return [ObservationEntity.from_dict(doc) for doc in docs]

    async def get_by_loop_id(
        self,
        loop_id: str
    ) -> List[ObservationEntity]:
        """Get observations for a specific loop"""
        projection = BaseMongoAdapter.entity_projection(ObservationEntity)
        docs = await self._adapter.find_many(
            {"loop_id": loop_id},
            projection=projection,
            sort=[("created_at", 1)]
        )
        return [ObservationEntity.from_dict(doc) for doc in docs]

    async def get_by_type(
        self,
        session_id: str,
        observation_type: ObservationType,
        limit: int = 100
    ) -> List[ObservationEntity]:
        """Get observations by type for a session"""
        projection = BaseMongoAdapter.entity_projection(ObservationEntity)
        docs = await self._adapter.find_many(
            {
                "session_id": session_id,
                "observation_type": observation_type.value
            },
            projection=projection,
            limit=limit,
            sort=[("created_at", -1)]
        )
        return [ObservationEntity.from_dict(doc) for doc in docs]

    async def get_errors_by_session_id(
        self,
        session_id: str
    ) -> List[ObservationEntity]:
        """Get error observations for a session"""
        projection = BaseMongoAdapter.entity_projection(ObservationEntity)
        docs = await self._adapter.find_many(
            {
                "session_id": session_id,
                "is_error": True
            },
            projection=projection,
            sort=[("created_at", -1)]
        )
        return [ObservationEntity.from_dict(doc) for doc in docs]

    async def count_by_session_id(self, session_id: str) -> int:
        """Count observations for a session"""
        return await self._adapter.count_documents({"session_id": session_id})
