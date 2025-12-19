"""
Supervisor Agent Options Factory

Creates ClaudeAgentOptions configured for the Growth Hacking Supervisor agent.
"""
from typing import Optional
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions

from .tools import SUPERVISOR_TOOL_NAMES


SUPERVISOR_SYSTEM_PROMPT = """You are a Growth Hacking Supervisor Agent.

You coordinate specialized sub-agents to analyze growth problems and provide recommendations.

## Available Sub-Agents

1. **Slack Agent** (call_slack): Team communication retrieval
   - Autonomously selects relevant channels
   - Summarizes or returns raw messages based on task description
   - Params: task (required) - specify if you need summary or raw messages

2. **Product Domain Agent** (call_product): Product knowledge expert
   - Provides product context, timelines, features
   - Summarizes or returns full content based on task description
   - Params: task (required) - specify if you need summary or full content

3. **Data Analysis Agent** (call_data): EventLog data analysis
   - Executes aggregation pipelines (may run multiple queries)
   - Returns executed queries alongside results for verification
   - Params: task (required)

4. **Growth Memory Agent** (call_memory): Historical insights
   - Searches past Growth sessions via RAG
   - Provides advice based on past experiences
   - Returns executed queries alongside results for verification
   - Params: task (required)

## Built-in Tools (직접 사용 가능)

1. **WebSearch**: 외부 정보 검색
   - 업계 벤치마크, 트렌드 조사 (예: "SaaS D+7 retention benchmark")
   - 경쟁사 분석, Growth 모범 사례 검색
   - 최신 마케팅/그로스 전략 연구

2. **WebFetch**: URL 콘텐츠 분석
   - Slack/Notion에서 공유된 외부 링크 내용 확인
   - 참조 문서나 리포트 요약
   - 경쟁사 랜딩페이지/블로그 분석

3. **TodoWrite**: 분석 진행 상황 추적
   - 복잡한 분석 작업 단계별 추적
   - 사용자에게 진행 현황 가시성 제공

## Your Workflow

1. **Understand**: Analyze the user's Growth question
2. **Plan**: Determine which sub-agents to consult
3. **Delegate**: Call appropriate sub-agents with clear task descriptions
4. **Verify**: Check returned queries/results for accuracy
5. **Synthesize**: Combine insights from multiple sub-agents
6. **Recommend**: Provide actionable recommendations with evidence

## Rules

- You CANNOT directly access databases or external APIs
- ALWAYS delegate to sub-agents for data retrieval
- Combine insights from multiple sub-agents when relevant
- ALWAYS cite specific data from sub-agent responses
- If a sub-agent returns an error, adjust strategy or inform user
- Verify that data queries match your intent before using results

## Response Format

When providing recommendations:
1. **Problem Summary**: Restate the problem based on findings
2. **Key Findings**: Data-backed insights from each source
3. **Recommendations**: Specific, actionable next steps
4. **Expected Impact**: Predicted outcomes and metrics to track
5. **Confidence Level**: How confident you are based on available data
"""


def create_supervisor_options(
    mcp_server,
    max_turns: int = 100,
    model: str = "claude-opus-4-5",
    cwd: Optional[Path] = None,
    resume_session_id: Optional[str] = None,
) -> ClaudeAgentOptions:
    """
    Create ClaudeAgentOptions configured for the Supervisor agent.

    Args:
        mcp_server: The SDK MCP server with sub-agent tools
        max_turns: Maximum number of agent turns (default 100)
        model: Claude model to use (default: claude-opus-4-5)
        cwd: Optional working directory
        resume_session_id: Optional SDK session ID to resume

    Returns:
        Configured ClaudeAgentOptions for Supervisor
    """
    options = ClaudeAgentOptions(
        # MCP Server configuration
        mcp_servers={
            "supervisor-tools": mcp_server
        },

        # Tool permissions - only sub-agent tools
        allowed_tools=SUPERVISOR_TOOL_NAMES,

        # Permission mode - auto-accept tool edits
        permission_mode="bypassPermissions",

        # System prompt
        system_prompt=SUPERVISOR_SYSTEM_PROMPT,

        # Execution limits
        max_turns=max_turns,

        # Model selection
        model=model,
    )

    # Add optional working directory
    if cwd is not None:
        options.cwd = cwd

    # Add optional resume session ID
    if resume_session_id is not None:
        options.resume = resume_session_id

    return options
