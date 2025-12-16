"""MongoDB Agent Session Repository Implementation"""
from typing import Optional, List
from datetime import datetime, timezone
from bson import ObjectId
from loguru import logger
from adapters.mongodb.base import BaseMongoAdapter
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from domain.entities.agent_session import AgentSessionEntity
from domain.ports.agent_session import AgentSessionRepository
from domain.value_objects.agent_enums import SessionStatus


class MongoAgentSessionRepository(AgentSessionRepository):
    """MongoDB implementation of AgentSessionRepository"""

    def __init__(self, adapter: AgentSessionAdapter):
        self._adapter = adapter

    async def create(self, entity: AgentSessionEntity) -> str:
        """Create new agent session"""
        doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
        result = await self._adapter.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, session_id: str) -> Optional[AgentSessionEntity]:
        """Retrieve agent session by ID"""
        projection = BaseMongoAdapter.entity_projection(AgentSessionEntity)
        try:
            doc = await self._adapter.find_one({"_id": ObjectId(session_id)}, projection)
        except Exception as e:
            logger.error(f"Invalid session_id format '{session_id}': {e}")
            return None

        if not doc:
            return None

        try:
            return AgentSessionEntity.from_dict(doc)
        except (ValueError, KeyError) as e:
            logger.error(f"Data validation failed for session_id '{session_id}': {e}")
            raise

    async def update_status(
        self,
        session_id: str,
        status: SessionStatus,
        error_message: Optional[str] = None
    ) -> bool:
        """Update session status"""
        update_doc = {
            "$set": {
                "status": status.value,
                "updated_at": datetime.now(timezone.utc)
            }
        }
        if error_message is not None:
            update_doc["$set"]["error_message"] = error_message

        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(session_id)},
                update_doc
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update status for session_id '{session_id}': {e}")
            return False

    async def increment_loop_count(self, session_id: str) -> bool:
        """Increment the current loop count"""
        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$inc": {"current_loop_count": 1},
                    "$set": {"updated_at": datetime.now(timezone.utc)}
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to increment loop count for session_id '{session_id}': {e}")
            return False

    async def set_hitl_request(
        self,
        session_id: str,
        hitl_request: dict
    ) -> bool:
        """Set HITL request and update status to WAITING_HITL"""
        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$set": {
                        "hitl_request": hitl_request,
                        "status": SessionStatus.WAITING_HITL.value,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to set HITL request for session_id '{session_id}': {e}")
            return False

    async def clear_hitl_request(self, session_id: str) -> bool:
        """Clear HITL request after response received"""
        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$set": {
                        "hitl_request": None,
                        "status": SessionStatus.PROCESSING.value,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to clear HITL request for session_id '{session_id}': {e}")
            return False

    async def set_final_decision(
        self,
        session_id: str,
        final_decision: dict
    ) -> bool:
        """Set final decision and mark session as COMPLETED"""
        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(session_id)},
                {
                    "$set": {
                        "final_decision": final_decision,
                        "status": SessionStatus.COMPLETED.value,
                        "updated_at": datetime.now(timezone.utc)
                    }
                }
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to set final decision for session_id '{session_id}': {e}")
            return False

    async def get_by_status(
        self,
        status: SessionStatus,
        limit: int = 100
    ) -> List[AgentSessionEntity]:
        """Get sessions by status"""
        projection = BaseMongoAdapter.entity_projection(AgentSessionEntity)
        docs = await self._adapter.find_many(
            {"status": status.value},
            projection=projection,
            limit=limit,
            sort=[("created_at", -1)]
        )
        return [AgentSessionEntity.from_dict(doc) for doc in docs]
