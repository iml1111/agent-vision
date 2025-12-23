"""Query messages for a session to debug sub-agent event storage."""
import asyncio
import sys
from pprint import pprint

# Add src to path
sys.path.insert(0, "src")

from config import Config
from adapters.mongodb.client import MongoDBClient


async def main():
    session_id = "694a377a7853827d51340b1f"

    config = Config()
    db_client = MongoDBClient(config.mongodb_uri, config.mongodb_name)

    # Get Message collection
    db = db_client._client[config.mongodb_name]
    collection = db["Message"]

    # Query messages for the session
    cursor = collection.find({"session_id": session_id}).sort("created_at", 1)
    messages = await cursor.to_list(length=100)

    print(f"\n{'='*80}")
    print(f"Session: {session_id}")
    print(f"Total messages: {len(messages)}")
    print(f"{'='*80}\n")

    for i, msg in enumerate(messages, 1):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")[:200]  # Truncate
        metadata = msg.get("metadata") or {}
        event_type = metadata.get("event_type", "-")

        print(f"[{i}] Role: {role}")
        print(f"    Event Type: {event_type}")
        print(f"    Content: {content}...")
        if metadata:
            print(f"    Metadata keys: {list(metadata.keys())}")
        print()

    # Summary by role
    print(f"\n{'='*80}")
    print("Summary by Role:")
    print(f"{'='*80}")
    role_counts = {}
    for msg in messages:
        role = msg.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")

    db_client.close()


if __name__ == "__main__":
    asyncio.run(main())
