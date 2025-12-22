#!/usr/bin/env python3
"""
Agent Chat CLI - POC for testing Agent API

Interactive CLI for testing the Agent API endpoints.
Automatically creates a new session and starts the conversation.

Usage:
    python scripts/agent_chat.py
"""
import asyncio
import sys

import httpx

BASE_URL = "http://localhost:8000"

# ANSI color codes
class Colors:
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    RESET = "\033[0m"


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
        interval: float = 3.0,
        max_attempts: int = 100
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
                print("\r" + " " * 30 + "\r", end="", flush=True)
                return status

            if status == "archived":
                print("\r" + " " * 30 + "\r", end="", flush=True)
                return status

            spin_char = spinner[attempt % len(spinner)]
            print(f"\r[Processing...] {spin_char}", end="", flush=True)

            await asyncio.sleep(interval)
            attempt += 1

        print("\r" + " " * 30 + "\r", end="", flush=True)
        return "timeout"


def print_header():
    """Print CLI header"""
    print(f"{Colors.CYAN}{'═' * 50}")
    print(f"  🤖 Agent Chat CLI")
    print(f"{'═' * 50}{Colors.RESET}")
    print(f"{Colors.DIM}Base URL: {BASE_URL}{Colors.RESET}")
    print()


def print_message(msg: dict) -> None:
    """Print a message with appropriate formatting based on type."""
    metadata = msg.get("metadata", {})
    event_type = metadata.get("event_type", "text")
    content = msg.get("content", "(no content)")

    if event_type == "subagent_call":
        subagent = metadata.get("subagent", "unknown")
        task = metadata.get("task", content)
        print(f"{Colors.DIM}   🔧 [{subagent}] {task}{Colors.RESET}")
    else:
        print(f"{Colors.GREEN}🤖 Agent:{Colors.RESET} {content}")


async def chat_loop(client: AgentChatClient, session_id: str):
    """
    Main chat loop.

    Args:
        client: API client
        session_id: Active session ID
    """
    print()
    print(f"{Colors.DIM}{'─' * 50}{Colors.RESET}")
    print()

    last_message_count = 0

    try:
        messages_data = await client.get_messages(session_id)
        last_message_count = messages_data.get("total_count", 0)
    except Exception:
        pass

    while True:
        try:
            user_input = input(f"{Colors.CYAN}{Colors.BOLD}🧑 You:{Colors.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{Colors.DIM}Goodbye!{Colors.RESET}")
            break

        if not user_input:
            continue

        try:
            await client.send_message(session_id, user_input)
        except httpx.HTTPStatusError as e:
            print(f"Error sending message: {e.response.status_code}")
            if e.response.status_code == 400:
                error_detail = e.response.json().get("detail", "Unknown error")
                print(f"  Detail: {error_detail}")
            continue

        final_status = await client.poll_until_active(session_id)

        if final_status == "timeout":
            print("Response timeout. Try again later.")
            continue

        if final_status == "archived":
            print("Session has been archived. Please start a new session.")
            break

        try:
            messages_data = await client.get_messages(session_id)
            messages = messages_data.get("messages", [])
            new_count = messages_data.get("total_count", 0)

            if new_count > last_message_count:
                # Extract only new assistant messages
                new_messages = [
                    m for m in messages[last_message_count:]
                    if m.get("role") == "assistant"
                ]

                print()  # Empty line before messages
                for msg in new_messages:
                    print_message(msg)
                print()  # Empty line after messages

            last_message_count = new_count

        except Exception as e:
            print(f"Error getting response: {e}")


async def main():
    """Main entry point"""
    print_header()

    client = AgentChatClient(BASE_URL)

    try:
        print(f"{Colors.DIM}Creating new session...{Colors.RESET}")
        result = await client.create_session()
        session_id = result["session_id"]
        print(f"{Colors.DIM}Session: {session_id}{Colors.RESET}")

        await chat_loop(client, session_id)

    except httpx.ConnectError:
        print(f"{Colors.YELLOW}Error: Cannot connect to {BASE_URL}{Colors.RESET}")
        print(f"{Colors.DIM}Make sure the API server is running.{Colors.RESET}")
        sys.exit(1)

    except Exception as e:
        print(f"{Colors.YELLOW}Error: {e}{Colors.RESET}")
        sys.exit(1)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
