#!/usr/bin/env python3
"""
Archive Session Script

Archives a session by setting its status to 'archived'.
Enqueues memory extraction task to SQS for async processing.

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
from adapters.aws.sqs_producer import SQSProducerAdapter


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
    sqs_producer = SQSProducerAdapter(
        queue_url=config.sqs_queue_url,
        aws_access_key_id=config.aws_access_key_id,
        aws_secret_access_key=config.aws_secret_access_key,
        region_name=config.aws_region
    )

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

        # Enqueue memory extraction task
        sqs_producer.enqueue_task(
            task_type="archive_session_to_memory",
            data={"session_id": args.session_id}
        )
        print(f"  Memory extraction task enqueued")

    finally:
        db_client.close()


if __name__ == "__main__":
    asyncio.run(main())
