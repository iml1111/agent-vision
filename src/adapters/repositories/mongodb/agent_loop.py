"""MongoDB Agent Loop Repository Implementation"""
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from bson import ObjectId
from loguru import logger
from adapters.mongodb.base import BaseMongoAdapter
from adapters.mongodb.collections.agent_loop_adapter import AgentLoopAdapter
from domain.entities.agent_loop import AgentLoopEntity
from domain.ports.agent_loop import AgentLoopRepository
from domain.value_objects.agent_enums import LoopPhase


class MongoAgentLoopRepository(AgentLoopRepository):
    """MongoDB implementation of AgentLoopRepository"""

    def __init__(self, adapter: AgentLoopAdapter):
        self._adapter = adapter

    async def create(self, entity: AgentLoopEntity) -> str:
        """Create new agent loop"""
        doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
        result = await self._adapter.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, loop_id: str) -> Optional[AgentLoopEntity]:
        """Retrieve agent loop by ID"""
        projection = BaseMongoAdapter.entity_projection(AgentLoopEntity)
        try:
            doc = await self._adapter.find_one({"_id": ObjectId(loop_id)}, projection)
        except Exception as e:
            logger.error(f"Invalid loop_id format '{loop_id}': {e}")
            return None

        if not doc:
            return None

        try:
            return AgentLoopEntity.from_dict(doc)
        except (ValueError, KeyError) as e:
            logger.error(f"Data validation failed for loop_id '{loop_id}': {e}")
            raise

    async def get_by_session_id(
        self,
        session_id: str,
        limit: int = 100
    ) -> List[AgentLoopEntity]:
        """Get all loops for a session"""
        projection = BaseMongoAdapter.entity_projection(AgentLoopEntity)
        docs = await self._adapter.find_many(
            {"session_id": session_id},
            projection=projection,
            limit=limit,
            sort=[("iteration", 1)]
        )
        return [AgentLoopEntity.from_dict(doc) for doc in docs]

    async def get_latest_by_session_id(
        self,
        session_id: str
    ) -> Optional[AgentLoopEntity]:
        """Get the latest loop for a session"""
        projection = BaseMongoAdapter.entity_projection(AgentLoopEntity)
        docs = await self._adapter.find_many(
            {"session_id": session_id},
            projection=projection,
            limit=1,
            sort=[("iteration", -1)]
        )
        if not docs:
            return None
        return AgentLoopEntity.from_dict(docs[0])

    async def update_phase(
        self,
        loop_id: str,
        phase: LoopPhase
    ) -> bool:
        """Update loop phase"""
        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(loop_id)},
                {
                    "$set": {
                        "phase": phase.value,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update phase for loop_id '{loop_id}': {e}")
            return False

    async def set_phase_output(
        self,
        loop_id: str,
        phase: LoopPhase,
        output: Dict[str, Any]
    ) -> bool:
        """Set output for a specific phase"""
        phase_field = f"{phase.value}_output"
        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(loop_id)},
                {
                    "$set": {
                        phase_field: output,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to set {phase_field} for loop_id '{loop_id}': {e}")
            return False
