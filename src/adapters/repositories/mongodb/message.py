"""MongoDB Message Repository Implementation"""
from typing import List, Optional

from bson import ObjectId
from loguru import logger

from adapters.mongodb.base import BaseMongoAdapter
from adapters.mongodb.collections.message_adapter import MessageAdapter
from domain.entities.message import MessageEntity
from domain.ports.message import MessageRepository


class MongoMessageRepository(MessageRepository):
    """MongoDB implementation of MessageRepository"""

    def __init__(self, adapter: MessageAdapter):
        self._adapter = adapter

    async def create(self, entity: MessageEntity) -> str:
        """Create new message"""
        doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
        result = await self._adapter.insert_one(doc)
        return str(result.inserted_id)

    async def get_by_id(self, message_id: str) -> Optional[MessageEntity]:
        """Retrieve message by ID"""
        projection = BaseMongoAdapter.entity_projection(MessageEntity)
        try:
            doc = await self._adapter.find_one({"_id": ObjectId(message_id)}, projection)
        except Exception as e:
            logger.error(f"Invalid message_id format '{message_id}': {e}")
            return None

        if not doc:
            return None

        try:
            return MessageEntity.from_dict(doc)
        except (ValueError, KeyError) as e:
            logger.error(f"Data validation failed for message_id '{message_id}': {e}")
            raise

    async def get_by_session_id(
        self,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[MessageEntity]:
        """Get messages for a session (ordered by created_at ascending)"""
        projection = BaseMongoAdapter.entity_projection(MessageEntity)
        docs = await self._adapter.find_many(
            {"session_id": session_id},
            projection=projection,
            limit=limit,
            skip=offset,
            sort=[("created_at", 1)]  # Ascending order for conversation flow
        )
        return [MessageEntity.from_dict(doc) for doc in docs]

    async def count_by_session_id(self, session_id: str) -> int:
        """Count messages in a session"""
        return await self._adapter.count_documents({"session_id": session_id})

    async def delete_by_session_id(self, session_id: str) -> int:
        """Delete all messages for a session"""
        result = await self._adapter.delete_many({"session_id": session_id})
        return result.deleted_count
