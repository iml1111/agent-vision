#!/usr/bin/env python3
"""
Agent Chat CLI - POC for testing Agent API

Interactive CLI for testing the Agent API endpoints.
Supports session creation, message sending with polling, and conversation history.

Usage:
    python scripts/agent_chat.py [--base-url http://localhost:8000] [--session-id <id>]
"""
import argparse
import asyncio
import sys
from typing import Optional

import httpx


class AgentChatClient:
    """HTTP client for Agent API"""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v1/agent"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def create_session(self) -> dict:
        """Create new agent session"""
        response = await self.client.post(f"{self.api_base}/sessions", json={})
        response.raise_for_status()
        return response.json()

    async def send_message(self, session_id: str, content: str) -> dict:
        """Send message to session (async enqueue)"""
        response = await self.client.post(
            f"{self.api_base}/sessions/{session_id}/messages",
            json={"content": content}
        )
        response.raise_for_status()
        return response.json()

    async def get_status(self, session_id: str) -> dict:
        """Get session status"""
        response = await self.client.get(
            f"{self.api_base}/sessions/{session_id}/status"
        )
        response.raise_for_status()
        return response.json()

    async def get_messages(self, session_id: str, limit: int = 50) -> dict:
        """Get conversation messages"""
        response = await self.client.get(
            f"{self.api_base}/sessions/{session_id}/messages",
            params={"limit": limit}
        )
        response.raise_for_status()
        return response.json()

    async def poll_until_active(
        self,
        session_id: str,
        interval: float = 1.0,
        max_attempts: int = 300
    ) -> str:
        """
        Poll status until session becomes active.

        Args:
            session_id: Session ID to poll
            interval: Polling interval in seconds
            max_attempts: Maximum polling attempts (default 5 minutes)

        Returns:
            Final status string
        """
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        attempt = 0

        while attempt < max_attempts:
            status_data = await self.get_status(session_id)
            status = status_data.get("status", "unknown")

            if status == "active":
                # Clear spinner line
                print("\r" + " " * 30 + "\r", end="", flush=True)
                return status

            if status == "archived":
                print("\r" + " " * 30 + "\r", end="", flush=True)
                return status

            # Show spinner
            spin_char = spinner[attempt % len(spinner)]
            print(f"\r[Processing...] {spin_char}", end="", flush=True)

            await asyncio.sleep(interval)
            attempt += 1

        print("\r" + " " * 30 + "\r", end="", flush=True)
        return "timeout"


def print_header(base_url: str):
    """Print CLI header"""
    print("=" * 50)
    print("  Agent Chat CLI - POC")
    print("=" * 50)
    print(f"Base URL: {base_url}")
    print()


async def select_session(client: AgentChatClient, session_id: Optional[str]) -> str:
    """
    Select or create a session.

    Args:
        client: API client
        session_id: Pre-specified session ID (from args)

    Returns:
        Session ID to use
    """
    if session_id:
        print(f"Using existing session: {session_id}")
        return session_id

    print("Select session:")
    print("[1] Create new session")
    print("[2] Enter existing session ID")

    while True:
        choice = input("Choice (1/2): ").strip()

        if choice == "1":
            print("Creating new session...")
            result = await client.create_session()
            new_session_id = result["session_id"]
            print(f"Session created: {new_session_id}")
            return new_session_id

        elif choice == "2":
            existing_id = input("Enter session ID: ").strip()
            if existing_id:
                # Validate session exists
                try:
                    await client.get_status(existing_id)
                    print(f"Session found: {existing_id}")
                    return existing_id
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 404:
                        print("Session not found. Try again.")
                    else:
                        print(f"Error: {e}")
            else:
                print("Invalid session ID. Try again.")

        else:
            print("Invalid choice. Enter 1 or 2.")


async def chat_loop(client: AgentChatClient, session_id: str):
    """
    Main chat loop.

    Args:
        client: API client
        session_id: Active session ID
    """
    print()
    print("Type 'exit' or 'quit' to end conversation.")
    print("Type 'history' to show conversation history.")
    print("-" * 50)
    print()

    # Track message count to find new messages
    last_message_count = 0

    # Get initial message count
    try:
        messages_data = await client.get_messages(session_id)
        last_message_count = messages_data.get("total_count", 0)
    except Exception:
        pass

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        # Handle special commands
        if user_input.lower() in ("exit", "quit"):
            print("Goodbye!")
            break

        if user_input.lower() == "history":
            await show_history(client, session_id)
            continue

        # Send message
        try:
            await client.send_message(session_id, user_input)
        except httpx.HTTPStatusError as e:
            print(f"Error sending message: {e.response.status_code}")
            if e.response.status_code == 400:
                error_detail = e.response.json().get("detail", "Unknown error")
                print(f"  Detail: {error_detail}")
            continue

        # Poll until active
        final_status = await client.poll_until_active(session_id)

        if final_status == "timeout":
            print("Response timeout. Try again later.")
            continue

        if final_status == "archived":
            print("Session has been archived. Please start a new session.")
            break

        # Get and display new assistant message
        try:
            messages_data = await client.get_messages(session_id)
            messages = messages_data.get("messages", [])
            new_count = messages_data.get("total_count", 0)

            # Find new assistant messages
            if new_count > last_message_count:
                for msg in messages:
                    if msg.get("role") == "assistant":
                        # Check if this is a new message (simple heuristic: last one)
                        pass

                # Get the last assistant message
                assistant_messages = [m for m in messages if m.get("role") == "assistant"]
                if assistant_messages:
                    latest = assistant_messages[-1]
                    print(f"\nAgent: {latest.get('content', '(no content)')}\n")

            last_message_count = new_count

        except Exception as e:
            print(f"Error getting response: {e}")


async def show_history(client: AgentChatClient, session_id: str):
    """Show conversation history"""
    print()
    print("-" * 50)
    print("Conversation History")
    print("-" * 50)

    try:
        messages_data = await client.get_messages(session_id)
        messages = messages_data.get("messages", [])

        if not messages:
            print("(no messages)")
        else:
            for msg in messages:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")
                prefix = "You" if role == "user" else "Agent"
                print(f"{prefix}: {content}")
                print()

    except Exception as e:
        print(f"Error: {e}")

    print("-" * 50)
    print()


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Agent Chat CLI - POC for testing Agent API"
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Resume existing session by ID"
    )

    args = parser.parse_args()

    # Print header
    print_header(args.base_url)

    # Create client
    client = AgentChatClient(args.base_url)

    try:
        # Select or create session
        session_id = await select_session(client, args.session_id)

        # Run chat loop
        await chat_loop(client, session_id)

    except httpx.ConnectError:
        print(f"Error: Cannot connect to {args.base_url}")
        print("Make sure the API server is running.")
        sys.exit(1)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
