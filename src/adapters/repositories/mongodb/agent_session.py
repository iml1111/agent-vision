"""MongoDB Agent Session Repository Implementation"""
from datetime import datetime, timezone
from typing import List, Optional
from logging_config import get_logger

from bson import ObjectId
from adapters.mongodb.base import BaseMongoAdapter
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from domain.entities.agent_session import AgentSessionEntity
from domain.ports.agent_session import AgentSessionRepository
from domain.value_objects.agent_enums import SessionStatus

logger = get_logger(__name__)


class MongoAgentSessionRepository(AgentSessionRepository):
    """MongoDB implementation of AgentSessionRepository (conversational model)"""

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
        status: SessionStatus
    ) -> bool:
        """Update session status"""
        update_doc = {
            "$set": {
                "status": status.value,
                "updated_at": datetime.now(timezone.utc)
            }
        }

        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(session_id)},
                update_doc
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update status for session_id '{session_id}': {e}")
            return False

    async def archive_session(self, session_id: str) -> bool:
        """Archive a session"""
        now = datetime.now(timezone.utc)
        update_doc = {
            "$set": {
                "status": SessionStatus.ARCHIVED.value,
                "archived_at": now,
                "updated_at": now
            }
        }

        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(session_id)},
                update_doc
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to archive session_id '{session_id}': {e}")
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

    async def delete(self, session_id: str) -> bool:
        """Delete a session"""
        try:
            result = await self._adapter.delete_one({"_id": ObjectId(session_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete session_id '{session_id}': {e}")
            return False

    async def update_claude_session_id(
        self,
        session_id: str,
        claude_session_id: str
    ) -> bool:
        """Update Claude session ID for resume capability"""
        update_doc = {
            "$set": {
                "claude_session_id": claude_session_id,
                "updated_at": datetime.now(timezone.utc)
            }
        }

        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(session_id)},
                update_doc
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to update Claude session ID for '{session_id}': {e}")
            return False

    async def clear_claude_session_id(self, session_id: str) -> bool:
        """Clear Claude session ID when session expires"""
        update_doc = {
            "$set": {
                "claude_session_id": None,
                "updated_at": datetime.now(timezone.utc)
            }
        }

        try:
            result = await self._adapter.update_one(
                {"_id": ObjectId(session_id)},
                update_doc
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Failed to clear Claude session ID for '{session_id}': {e}")
            return False
