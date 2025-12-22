#!/usr/bin/env python3
"""
Reset Sessions Script

Deletes all AgentSession and Message documents.
Use with caution - this is irreversible!

Usage:
    python scripts/reset_sessions.py
"""
import asyncio
import sys

sys.path.insert(0, "src")

from config import Config
from adapters.mongodb.client import MongoDBClient


async def main():
    config = Config()
    db_client = MongoDBClient(config.mongodb_uri, config.mongodb_name)

    try:
        db = db_client.db

        # Count documents
        session_count = await db["AgentSession"].count_documents({})
        message_count = await db["Message"].count_documents({})

        print(f"Found {session_count} sessions and {message_count} messages")

        if session_count == 0 and message_count == 0:
            print("Nothing to delete.")
            return

        # Delete
        session_result = await db["AgentSession"].delete_many({})
        message_result = await db["Message"].delete_many({})

        print(f"Deleted {session_result.deleted_count} sessions")
        print(f"Deleted {message_result.deleted_count} messages")
        print("Reset complete.")

    finally:
        db_client.close()


if __name__ == "__main__":
    asyncio.run(main())
