"""
MongoDB Index Setup Script

Creates all required indexes for the Growth Agent system.
Run this script after setting up MongoDB.

Standard indexes are created via pymongo.
Vector search index must be created via MongoDB Atlas UI or API.

Usage:
    python scripts/setup_mongodb_indexes.py
"""
import asyncio
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger


# Index definitions
INDEXES = {
    "AgentSession": [
        {"keys": [("status", 1), ("created_at", -1)], "name": "status_created_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
    ],
    "AgentLoop": [
        {"keys": [("session_id", 1), ("created_at", -1)], "name": "session_created_idx"},
        {"keys": [("session_id", 1), ("iteration", 1)], "name": "session_iteration_idx"},
    ],
    "Observation": [
        {"keys": [("session_id", 1), ("created_at", -1)], "name": "session_created_idx"},
        {"keys": [("session_id", 1), ("loop_id", 1)], "name": "session_loop_idx"},
        {"keys": [("observation_type", 1), ("created_at", -1)], "name": "type_created_idx"},
    ],
    "GrowthMemory": [
        {"keys": [("memory_type", 1), ("created_at", -1)], "name": "type_created_idx"},
        {"keys": [("source_session_id", 1)], "name": "source_session_idx"},
        {"keys": [("tags", 1)], "name": "tags_idx"},
        {"keys": [("created_at", -1)], "name": "created_at_idx"},
    ],
}


# Vector Search Index definition (for Atlas)
VECTOR_SEARCH_INDEX = {
    "name": "growth_memory_vector_index",
    "definition": {
        "mappings": {
            "dynamic": True,
            "fields": {
                "embedding": {
                    "type": "knnVector",
                    "dimensions": 1536,
                    "similarity": "cosine"
                },
                "memory_type": {
                    "type": "token"
                }
            }
        }
    }
}


async def create_standard_indexes(db) -> None:
    """Create standard MongoDB indexes."""
    for collection_name, indexes in INDEXES.items():
        collection = db[collection_name]

        for index_def in indexes:
            try:
                await collection.create_index(
                    index_def["keys"],
                    name=index_def["name"],
                    background=True
                )
                logger.info(f"Created index {index_def['name']} on {collection_name}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"Index {index_def['name']} already exists on {collection_name}")
                else:
                    logger.error(f"Failed to create index {index_def['name']} on {collection_name}: {e}")
                    raise


async def list_existing_indexes(db) -> None:
    """List all existing indexes for agent collections."""
    for collection_name in INDEXES.keys():
        collection = db[collection_name]
        indexes = await collection.index_information()
        logger.info(f"\n{collection_name} indexes:")
        for name, info in indexes.items():
            logger.info(f"  - {name}: {info.get('key', info)}")


async def main():
    """Main function to create all indexes."""
    # Get MongoDB URI from environment
    mongodb_uri = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    mongodb_name = os.getenv("MONGODB_NAME", "agent_vision")

    logger.info(f"Connecting to MongoDB: {mongodb_uri}")
    logger.info(f"Database: {mongodb_name}")

    # Connect to MongoDB
    client = AsyncIOMotorClient(mongodb_uri)
    db = client[mongodb_name]

    try:
        # Verify connection
        await client.admin.command("ping")
        logger.info("Successfully connected to MongoDB")

        # Create standard indexes
        logger.info("\n=== Creating Standard Indexes ===")
        await create_standard_indexes(db)

        # List all indexes
        logger.info("\n=== Current Index Status ===")
        await list_existing_indexes(db)

        # Print vector search index instructions
        logger.info("\n=== Vector Search Index (Manual Setup Required) ===")
        logger.info("The vector search index must be created via MongoDB Atlas UI or API.")
        logger.info("Collection: GrowthMemory")
        logger.info("Index Name: growth_memory_vector_index")
        logger.info("Configuration:")
        logger.info(f"  {VECTOR_SEARCH_INDEX['definition']}")
        logger.info("\nAtlas UI Steps:")
        logger.info("1. Go to Atlas > Database > Browse Collections")
        logger.info("2. Select the GrowthMemory collection")
        logger.info("3. Click 'Search Indexes' tab")
        logger.info("4. Click 'Create Search Index'")
        logger.info("5. Select 'JSON Editor' and paste the index definition")
        logger.info("6. Name it 'growth_memory_vector_index'")

        logger.info("\n=== Index Setup Complete ===")

    except Exception as e:
        logger.error(f"Error setting up indexes: {e}")
        raise
    finally:
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
