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

# ANSI color codes (Claude Code style)
class Colors:
    CYAN = "\033[96m"      # User prompt
    GREEN = "\033[92m"     # Success (✓)
    YELLOW = "\033[93m"    # Warning
    RED = "\033[91m"       # Error (✗)
    BLUE = "\033[94m"      # Agent name
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

    async def poll_and_stream(
        self,
        session_id: str,
        last_message_count: int,
        interval: float = 1.0,
        max_attempts: int = 200
    ) -> tuple[str, int]:
        """
        Poll status and stream new messages in real-time.

        Args:
            session_id: Session ID to poll
            last_message_count: Last known message count
            interval: Polling interval in seconds
            max_attempts: Maximum polling attempts

        Returns:
            Tuple of (final_status, new_message_count)
        """
        spinner = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        attempt = 0
        current_count = last_message_count
        first_output = True

        while attempt < max_attempts:
            # Get status and messages in parallel
            status_data = await self.get_status(session_id)
            status = status_data.get("status", "unknown")

            # Check for new messages
            messages_data = await self.get_messages(session_id)
            messages = messages_data.get("messages", [])
            new_count = messages_data.get("total_count", 0)

            # Print new messages immediately
            if new_count > current_count:
                # Clear spinner line
                print("\r" + " " * 40 + "\r", end="", flush=True)

                # Get new messages (assistant, sub-agents, and system)
                new_messages = [
                    m for m in messages[current_count:]
                    if m.get("role") != "user"
                ]

                if first_output and new_messages:
                    print()  # Empty line before first message
                    first_output = False

                for msg in new_messages:
                    print_message(msg)

                current_count = new_count

            # Check terminal conditions
            if status == "active":
                if not first_output:
                    print()  # Empty line after messages
                else:
                    print("\r" + " " * 40 + "\r", end="", flush=True)
                return status, current_count

            if status == "archived":
                print("\r" + " " * 40 + "\r", end="", flush=True)
                return status, current_count

            # Show spinner
            spin_char = spinner[attempt % len(spinner)]
            print(f"\r{spin_char} Processing...", end="", flush=True)

            await asyncio.sleep(interval)
            attempt += 1

        print("\r" + " " * 40 + "\r", end="", flush=True)
        return "timeout", current_count


def print_header():
    """Print CLI header"""
    print(f"\n{Colors.BOLD}Agent Chat{Colors.RESET}")
    print(f"─" * 40)
    print()


def print_message(msg: dict) -> None:
    """Print a message with Claude Code style formatting."""
    role = msg.get("role", "")
    metadata = msg.get("metadata", {}) or {}
    event_type = metadata.get("event_type", "text")
    content = msg.get("content", "")

    # Sub-agent event messages
    if role.startswith("subagent_"):
        agent_name = role.replace("subagent_", "").capitalize()

        if event_type == "tool_use":
            tool_name = metadata.get("tool_name", "unknown")
            # Extract short tool name (remove mcp__xxx__ prefix)
            short_name = tool_name.split("__")[-1] if "__" in tool_name else tool_name
            print(f"  {short_name}")

        elif event_type == "tool_result":
            tool_output = metadata.get("tool_output", "")
            is_error = metadata.get("is_error", False)
            # Create brief summary from output
            output_str = str(tool_output)
            if is_error:
                print(f"  {Colors.RED}✗{Colors.RESET} error")
            else:
                # Extract meaningful summary (first line or count)
                summary = output_str.split("\n")[0][:60]
                if len(output_str) > 60:
                    summary += "..."
                print(f"  {Colors.GREEN}✓{Colors.RESET} {summary}")

        else:
            # Text from sub-agent - show with indentation
            if content:
                # Indent multi-line content
                lines = content.split("\n")
                for line in lines[:3]:  # Show first 3 lines
                    print(f"  {line}")
                if len(lines) > 3:
                    print(f"  ...")

    # Supervisor calling a sub-agent
    elif event_type == "subagent_call":
        subagent = metadata.get("subagent", "unknown").capitalize()
        print(f"\n{Colors.BLUE}{Colors.BOLD}● {subagent}{Colors.RESET}")

    # System messages
    elif role == "system":
        print(f"{Colors.YELLOW}! {content}{Colors.RESET}")

    # Final assistant response (no decoration)
    else:
        if content:
            print(f"\n{content}")


async def chat_loop(client: AgentChatClient, session_id: str):
    """
    Main chat loop.

    Args:
        client: API client
        session_id: Active session ID
    """

    last_message_count = 0

    try:
        messages_data = await client.get_messages(session_id)
        last_message_count = messages_data.get("total_count", 0)
    except Exception:
        pass

    while True:
        try:
            user_input = input(f"{Colors.CYAN}>{Colors.RESET} ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        try:
            await client.send_message(session_id, user_input)
            # Increment count for user message
            last_message_count += 1
        except httpx.HTTPStatusError as e:
            print(f"Error sending message: {e.response.status_code}")
            if e.response.status_code == 400:
                error_detail = e.response.json().get("detail", "Unknown error")
                print(f"  Detail: {error_detail}")
            continue

        # Stream messages in real-time while polling status
        final_status, last_message_count = await client.poll_and_stream(
            session_id, last_message_count
        )

        if final_status == "timeout":
            print(f"{Colors.YELLOW}! Timeout{Colors.RESET}")
            continue

        if final_status == "archived":
            print(f"{Colors.YELLOW}! Session archived{Colors.RESET}")
            break


async def main():
    """Main entry point"""
    print_header()

    client = AgentChatClient(BASE_URL)

    try:
        result = await client.create_session()
        session_id = result["session_id"]

        await chat_loop(client, session_id)

    except httpx.ConnectError:
        print(f"{Colors.RED}✗{Colors.RESET} Cannot connect to {BASE_URL}")
        print("  Make sure the API server is running.")
        sys.exit(1)

    except Exception as e:
        print(f"{Colors.RED}✗{Colors.RESET} {e}")
        sys.exit(1)

    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
