"""
Debug script to verify sub-agent event saving.

After the fix: Sub-agent events should be saved immediately in tool functions,
so they appear in the Message collection with the correct roles.
"""
import asyncio
import sys

sys.path.insert(0, "src")

from config import Config
from adapters.mongodb.client import MongoDBClient
from adapters.mongodb.collections.eventlog_adapter import EventLogAdapter
from adapters.external.slack_client import SlackClient
from adapters.external.notion_client import NotionClient
from adapters.openai.embedding_client import OpenAIEmbeddingClient
from adapters.repositories.mongodb.growth_memory import MongoGrowthMemoryRepository
from adapters.repositories.mongodb.message import MongoMessageRepository
from adapters.agent.supervisor.client import SupervisorAgentClient
from domain.value_objects import AgentMessageType


async def main():
    config = Config()
    db_client = MongoDBClient(config.mongodb_uri, config.mongodb_name)

    # Initialize dependencies
    eventlog_adapter = EventLogAdapter(db_client.db)
    slack_client = SlackClient(config.slack_bot_token) if config.slack_bot_token else None
    notion_client = NotionClient(config.notion_api_key) if config.notion_api_key else None
    embedding_client = OpenAIEmbeddingClient(config.openai_api_key)

    from adapters.mongodb.collections.growth_memory_adapter import GrowthMemoryAdapter
    from adapters.mongodb.collections.message_adapter import MessageAdapter
    memory_repo = MongoGrowthMemoryRepository(GrowthMemoryAdapter(db_client.db))
    message_repo = MongoMessageRepository(MessageAdapter(db_client.db))

    # Generate unique session ID for this test
    from bson import ObjectId
    test_session_id = str(ObjectId())

    print("\n" + "="*80)
    print("DEBUG: Sub-agent Event Saving Verification")
    print("="*80)
    print(f"Test Session ID: {test_session_id}\n")

    async with SupervisorAgentClient(
        eventlog_adapter=eventlog_adapter,
        slack_client=slack_client,
        notion_client=notion_client,
        config=config,
        memory_repo=memory_repo,
        embedding_client=embedding_client,
        message_repo=message_repo,
        session_id=test_session_id,
    ) as client:
        # Simple query that should trigger data agent
        prompt = "레슬리 총 결제자 수를 알려줘"

        print(f"Query: {prompt}\n")
        print("-"*80)

        event_count = 0
        tool_calls = []
        async for event in client.stream_query(prompt):
            event_count += 1
            print(f"\n[Event #{event_count}] Type: {event.type}")

            if event.type == AgentMessageType.TOOL_USE and event.tool_call:
                print(f"  Tool: {event.tool_call.name}")
                print(f"  Tool ID: {event.tool_call.id}")
                tool_calls.append(event.tool_call.name)

            elif event.type == AgentMessageType.TEXT:
                content_preview = (event.content or "")[:100]
                print(f"  Content: {content_preview}...")

            elif event.type == AgentMessageType.COMPLETE:
                print(f"  Claude Session ID: {event.claude_session_id}")

    print("\n" + "="*80)
    print(f"Total events: {event_count}")
    print(f"Tool calls: {tool_calls}")
    print("="*80)

    # Query saved messages
    print("\n" + "="*80)
    print("Checking saved messages in DB...")
    print("="*80)

    db = db_client._client[config.mongodb_name]
    collection = db["Message"]
    cursor = collection.find({"session_id": test_session_id}).sort("created_at", 1)
    messages = await cursor.to_list(length=100)

    print(f"\nTotal messages saved: {len(messages)}\n")

    # Count by role
    role_counts = {}
    for msg in messages:
        role = msg.get("role", "unknown")
        role_counts[role] = role_counts.get(role, 0) + 1

    print("Messages by role:")
    for role, count in sorted(role_counts.items()):
        print(f"  {role}: {count}")

    # Check for sub-agent events
    subagent_roles = ["subagent_slack", "subagent_product", "subagent_data", "subagent_memory"]
    subagent_msgs = [m for m in messages if m.get("role") in subagent_roles]

    print(f"\nSub-agent messages: {len(subagent_msgs)}")
    if subagent_msgs:
        print("✅ SUCCESS: Sub-agent events are being saved!")
        for msg in subagent_msgs[:5]:  # Show first 5
            role = msg.get("role")
            metadata = msg.get("metadata") or {}
            event_type = metadata.get("event_type", "-")
            content_preview = (msg.get("content") or "")[:50]
            print(f"  - [{role}] {event_type}: {content_preview}...")
    else:
        print("❌ FAILURE: No sub-agent events saved!")

    # Cleanup test data
    await collection.delete_many({"session_id": test_session_id})
    print(f"\nCleaned up test messages for session {test_session_id}")

    db_client.close()


if __name__ == "__main__":
    asyncio.run(main())
