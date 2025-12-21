"""MongoDB SubAgentTrace Repository Implementation"""
from typing import List, Optional

from bson import ObjectId

from adapters.mongodb.base import BaseMongoAdapter
from adapters.mongodb.collections.subagent_trace_adapter import SubAgentTraceAdapter
from domain.entities.subagent_trace import SubAgentTraceEntity
from domain.ports.subagent_trace import SubAgentTraceRepository
from logging_config import get_logger

logger = get_logger(__name__)


class MongoSubAgentTraceRepository(SubAgentTraceRepository):
    """MongoDB implementation of SubAgentTraceRepository"""

    def __init__(self, adapter: SubAgentTraceAdapter):
        self._adapter = adapter

    async def create(self, entity: SubAgentTraceEntity) -> str:
        """Create new sub-agent trace document"""
        doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
        result = await self._adapter.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, trace_id: str) -> Optional[SubAgentTraceEntity]:
        """Retrieve trace by ID"""
        projection = BaseMongoAdapter.entity_projection(SubAgentTraceEntity)
        try:
            doc = await self._adapter.find_one({"_id": ObjectId(trace_id)}, projection)
        except Exception as e:
            logger.error(f"Invalid trace_id format '{trace_id}': {e}")
            return None

        if not doc:
            return None

        try:
            return SubAgentTraceEntity.from_dict(doc)
        except (ValueError, KeyError) as e:
            logger.error(f"Data validation failed for trace_id '{trace_id}': {e}")
            raise

    async def get_by_session_id(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[SubAgentTraceEntity]:
        """Retrieve all traces for a session"""
        projection = BaseMongoAdapter.entity_projection(SubAgentTraceEntity)
        docs = await self._adapter.find_many(
            {"session_id": session_id},
            projection=projection,
            limit=limit,
            skip=offset,
            sort=[("created_at", 1)]
        )

        results = []
        for doc in docs:
            try:
                entity = SubAgentTraceEntity.from_dict(doc)
                results.append(entity)
            except (ValueError, KeyError) as e:
                logger.error(f"Data validation failed for session_id '{session_id}': {e}")
                continue

        return results

    async def get_by_parent_message_id(
        self,
        parent_message_id: str
    ) -> Optional[SubAgentTraceEntity]:
        """Retrieve trace by parent message ID"""
        projection = BaseMongoAdapter.entity_projection(SubAgentTraceEntity)
        doc = await self._adapter.find_one(
            {"parent_message_id": parent_message_id},
            projection
        )

        if not doc:
            return None

        try:
            return SubAgentTraceEntity.from_dict(doc)
        except (ValueError, KeyError) as e:
            logger.error(
                f"Data validation failed for parent_message_id '{parent_message_id}': {e}"
            )
            raise

    async def delete(self, trace_id: str) -> bool:
        """Delete trace document"""
        try:
            result = await self._adapter.delete_one({"_id": ObjectId(trace_id)})
            return result.deleted_count > 0
        except Exception as e:
            logger.error(f"Failed to delete trace_id '{trace_id}': {e}")
            return False

    async def delete_by_session_id(self, session_id: str) -> int:
        """Delete all traces for a session"""
        result = await self._adapter.delete_many({"session_id": session_id})
        return result.deleted_count
