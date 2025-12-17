#!/usr/bin/env python3
"""
Archive Session Script

Archives a session by setting its status to 'archived'.
Future: Will migrate conversation to Growth Memory before archiving.

Usage:
    python scripts/archive_session.py <session_id>
"""
import argparse
import asyncio
import sys

sys.path.insert(0, "src")

from config import Config
from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.agent_session_adapter import AgentSessionAdapter
from adapters.repositories.mongodb.agent_session import MongoAgentSessionRepository


async def main():
    parser = argparse.ArgumentParser(
        description="Archive a session by ID"
    )
    parser.add_argument(
        "session_id",
        help="Session ID to archive"
    )
    args = parser.parse_args()

    # Initialize
    config = Config()
    db_client = MongoDBClient(config.MONGODB_URI, config.MONGODB_NAME)

    try:
        adapter = AgentSessionAdapter(db_client.database)
        repo = MongoAgentSessionRepository(adapter)

        # Get session
        session = await repo.get_by_id(args.session_id)
        if not session:
            print(f"Error: Session not found: {args.session_id}")
            sys.exit(1)

        # Check if already archived
        if session.status.value == "archived":
            print(f"Session already archived: {args.session_id}")
            sys.exit(0)

        # Archive session
        archived = session.archive()
        await repo.update(archived)

        print(f"Session archived successfully: {args.session_id}")
        print(f"  Previous status: {session.status.value}")
        print(f"  New status: archived")

    finally:
        db_client.close()


if __name__ == "__main__":
    asyncio.run(main())
