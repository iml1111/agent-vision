# Agent Vision

**Growth Hacking Agent Backend - DDD + Hexagonal Architecture**

AI 기반 Growth Hacking 에이전트 백엔드 시스템입니다. Plan→Act→Observe→Critique→Decide 루프를 통해 데이터 기반 성장 전략을 자동으로 분석하고 제안합니다.

## Features

- **Agent Orchestration**: Claude Agent SDK 기반 자율 에이전트 루프
- **HITL (Human-in-the-Loop)**: 중요 의사결정시 인간 개입 지원
- **Growth Memory**: Vector Search 기반 RAG 시스템으로 학습 컨텍스트 유지
- **External Tool Integration**: Slack, Notion, EventLog 연동
- **DDD + Hexagonal Architecture**: 확장 가능한 도메인 중심 설계

## Tech Stack

- **Runtime**: Python 3.9+
- **Framework**: FastAPI
- **Database**: MongoDB (Motor + Atlas Vector Search)
- **AI/LLM**: Claude Agent SDK, OpenAI Embeddings
- **Queue**: AWS SQS (optional)

## Quick Start

### 1. Clone and Setup

```bash
# Clone the repository
git clone <your-repo-url> agent-vision
cd agent-vision

# Create virtual environment
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r src/requirements.txt
```

### 2. Configure Environment

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your settings
vi .env
```

### 3. Run the Application

```bash
# API Server (development)
./void run api

# SQS Worker (optional)
./void run worker

# CLI Job
./void run job <JOB_NAME>
```

## Project Structure

```
src/
├── config/              # Configuration modules
│   └── allowlist.py     # Slack/Notion allowlist
├── domain/              # Pure Python domain logic
│   ├── entities/        # Domain entities
│   │   ├── agent_session.py
│   │   ├── agent_loop.py
│   │   ├── observation.py
│   │   └── growth_memory.py
│   ├── ports/           # Abstract interfaces
│   └── value_objects/   # Enums and value objects
├── service_layer/       # Application services
│   └── application/
│       ├── agent_orchestration_service.py
│       ├── observation_service.py
│       └── growth_memory_service.py
├── adapters/            # Infrastructure implementations
│   ├── openai/          # OpenAI embedding client
│   ├── external/        # Slack, Notion API clients
│   ├── agent/           # Claude Agent SDK integration
│   │   ├── mcp_server.py
│   │   ├── options.py
│   │   └── client.py
│   ├── agent_tools/     # Custom MCP tools
│   │   ├── eventlog_tool.py
│   │   ├── slack_tool.py
│   │   ├── notion_tool.py
│   │   └── growth_memory_tool.py
│   ├── agent_hooks/     # Agent lifecycle hooks
│   ├── mongodb/         # MongoDB adapters
│   ├── repositories/    # Repository implementations
│   └── uow/             # Unit of Work
├── entrypoints/         # Application entry points
│   ├── api/             # FastAPI
│   ├── worker/          # SQS Worker
│   └── cli/             # CLI Jobs
└── config.py            # Pydantic BaseSettings
```

## API Endpoints

### Core

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |

### Agent Sessions

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/agent/sessions` | Create agent session |
| POST | `/api/v1/agent/sessions/{id}/messages` | Send message (start/continue) |
| GET | `/api/v1/agent/sessions/{id}/status` | Poll session status |
| GET | `/api/v1/agent/sessions/{id}/observations` | Get session observations |
| POST | `/api/v1/agent/sessions/{id}/hitl` | Submit HITL response |
| DELETE | `/api/v1/agent/sessions/{id}` | Cancel session |

### Session Status Flow

```
[created] → POST /messages → [processing] → GET /status (poll)
                                   ↓
            [waiting_hitl] ← needs HITL → POST /hitl → [processing]
                                   ↓
                            [completed] → final_decision in response
```

## Agent System

### Loop Phases

```
Plan → Act → Observe → Critique → Decide
  │      │       │         │         │
  │      │       │         │         └─ CONTINUE / HITL_QUESTION / EXPERIMENT
  │      │       │         └─ Evaluate tool results
  │      │       └─ Capture observations via hooks
  │      └─ Execute MCP tools
  └─ Claude Agent reasoning
```

### Available Tools

| Tool | Description |
|------|-------------|
| `eventlog_*` | MongoDB analytics queries (funnel, retention) |
| `slack_*` | Slack channel access (allowlisted) |
| `notion_*` | Notion database access (allowlisted) |
| `growth_memory_*` | Vector search RAG |

### Decision Types

| Type | Description |
|------|-------------|
| `CONTINUE` | Need more information, continue loop |
| `HITL_QUESTION` | Request human input |
| `EXPERIMENT` | Recommend A/B test |
| `INSTRUMENTATION_TODO` | Need event tracking |

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `MONGODB_URI` | MongoDB connection URI | Yes |
| `MONGODB_NAME` | Database name | Yes |
| `ANTHROPIC_API_KEY` | Claude API key | Yes |
| `OPENAI_API_KEY` | OpenAI API key (embeddings) | Yes |
| `SLACK_BOT_TOKEN` | Slack bot token | Optional |
| `NOTION_API_KEY` | Notion API key | Optional |
| `AGENT_MAX_LOOP_COUNT` | Max agent loop iterations | No (default: 10) |
| `AGENT_HITL_TIMEOUT_SECONDS` | HITL response timeout | No (default: 3600) |
| `SLACK_CHANNEL_ALLOWLIST` | JSON array of allowed channels | Optional |
| `NOTION_DATABASE_ALLOWLIST` | JSON array of allowed databases | Optional |
| `NOTION_PAGE_ALLOWLIST` | JSON array of allowed pages | Optional |

## Development

### Adding a New Entity

1. Create entity in `domain/entities/`
2. Define repository port in `domain/ports/`
3. Implement MongoDB adapter in `adapters/mongodb/collections/`
4. Implement repository in `adapters/repositories/mongodb/`
5. Register in `adapters/uow/mongo_unit_of_work.py`

### Adding a New Agent Tool

1. Create tool in `adapters/agent_tools/xxx_tool.py` with `@tool` decorator
2. Register in `adapters/agent/mcp_server.py`
3. Add to `GROWTH_TOOL_NAMES` in `adapters/agent/options.py`

### Adding a New API Endpoint

1. Create schemas in `entrypoints/api/schemas/`
2. Create route handler in `entrypoints/api/routes/`
3. Register router in `entrypoints/api/routes/__init__.py`

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run integration tests (requires MongoDB)
pytest tests/integration/ -v
```

## Requirements

- Python 3.9+
- MongoDB (Replica Set for transactions)
- Anthropic API access (Claude)
- OpenAI API access (Embeddings)

## License

MIT License
