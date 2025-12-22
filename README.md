# Agent Vision

**Growth Hacking Agent Backend - DDD + Hexagonal Architecture**

AI 기반 Growth Hacking 에이전트 백엔드 시스템입니다. Claude Agent SDK를 활용하여 데이터 기반 성장 전략을 자동으로 분석하고 제안합니다.

## Features

- **Conversational Agent**: 연속 대화 기반 Growth 분석 (SDK Session Resume)
- **Async Processing**: SQS FIFO 기반 비동기 처리 (빠른 API 응답)
- **External Tool Integration**: Slack, Notion, EventLog 연동
- **DDD + Hexagonal Architecture**: 확장 가능한 도메인 중심 설계

## Tech Stack

- **Runtime**: Python 3.12+
- **Framework**: FastAPI
- **Database**: MongoDB (Motor)
- **AI/LLM**: Claude Agent SDK
- **Queue**: AWS SQS FIFO

## Quick Start

### Option 1: Docker (Recommended)

```bash
# 1. Clone repository
git clone <your-repo-url> agent-vision
cd agent-vision

# 2. Configure environment
cp .env.example .env
# Edit .env and fill in your API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, etc.)

# 3. Run with Docker Compose
docker-compose up --build

# API will be available at http://localhost:8000
# Both API and Worker start automatically

# 4. Test with Agent Chat CLI (in a new terminal)
python scripts/agent_chat.py
# Creates a new session and starts interactive chat with the agent
```

### Option 2: Local Development

```bash
# 1. Clone and setup
git clone <your-repo-url> agent-vision
cd agent-vision

python -m venv venv
source venv/bin/activate
pip install -r src/requirements.txt

# 2. Configure environment
cp .env.example .env
vi .env

# Allowlist 설정 (Slack/Notion 리소스 접근 제어)
cp src/allowlist.example.json src/allowlist.json
vi src/allowlist.json

# 3. Run (in separate terminals)
./void run api      # API Server
./void run worker   # SQS Worker
```

## Scripts

### Agent Chat CLI (POC)

API 테스트를 위한 대화형 CLI:

```bash
# 새 세션으로 시작
python scripts/agent_chat.py

# 기존 세션 이어서
python scripts/agent_chat.py --session-id <SESSION_ID>

# 다른 서버로 연결
python scripts/agent_chat.py --base-url http://localhost:8080
```

**기능:**
- 세션 생성/선택 → 대화 루프 (1초 polling) → `history` 조회 → `exit` 종료

### Archive Session

세션을 archived 상태로 변경:

```bash
python scripts/archive_session.py <SESSION_ID>
```

**출력 예시:**
```
Session archived successfully: 507f1f77bcf86cd799439011
  Previous status: active
  New status: archived
```

**Note:** 향후 Growth Memory로 대화 내용 마이그레이션 기능 추가 예정

## Project Structure

```
src/
├── config.py            # Pydantic BaseSettings (Allowlist 포함)
├── domain/              # Pure Python domain logic
│   ├── entities/        # agent_session.py, message.py
│   ├── ports/           # Repository interfaces
│   ├── value_objects/   # Enums and VOs
│   └── exceptions.py
├── service_layer/
│   └── application/
│       └── agent_orchestration_service.py
├── adapters/
│   ├── agent/           # Claude Agent SDK integration
│   │   ├── client.py    # GrowthAgentClient
│   │   ├── options.py   # Agent options
│   │   ├── mcp_server.py
│   │   ├── hooks/       # pre_tool_use, post_tool_use
│   │   └── tools/       # eventlog, slack, notion
│   ├── mongodb/         # MongoDB client, collections
│   ├── repositories/    # Repository implementations
│   ├── aws/             # SQS producer/consumer
│   ├── external/        # Slack, Notion API clients
│   └── uow/             # Unit of Work
├── entrypoints/
│   ├── api/             # FastAPI
│   └── worker/          # SQS Worker
└── __about__.py

scripts/
├── agent_chat.py        # POC CLI for API testing
└── archive_session.py   # Archive session utility
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/agent/sessions` | Create session |
| POST | `/api/v1/agent/sessions/{id}/messages` | Send message (async) |
| GET | `/api/v1/agent/sessions/{id}/messages` | Get conversation history |
| GET | `/api/v1/agent/sessions/{id}/status` | Get session status |
| DELETE | `/api/v1/agent/sessions/{id}` | Delete session |

### Client Usage Flow

```
1. POST /sessions → {"session_id": "...", "status": "active"}
2. POST /sessions/{id}/messages → {"status": "processing"}
3. GET /sessions/{id}/status (poll) → {"status": "active"}
4. GET /sessions/{id}/messages → [user_message, assistant_message]
```

### Session Status

| Status | Description |
|--------|-------------|
| `active` | 대화 진행 중 |
| `processing` | Worker에서 응답 생성 중 |
| `archived` | SDK 세션 만료 |

## Configuration

### Environment Variables

모든 환경변수는 필수입니다. `.env.example`을 참고하세요.

| Variable | Description |
|----------|-------------|
| `ENV` | 환경 (development, production) |
| `MONGODB_URI` | MongoDB connection URI |
| `MONGODB_NAME` | Database name |
| `ANTHROPIC_API_KEY` | Claude API key |
| `OPENAI_API_KEY` | OpenAI API key (Embeddings) |
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION` | AWS region |
| `SQS_QUEUE_URL` | SQS FIFO queue URL |
| `SLACK_BOT_TOKEN` | Slack bot token |
| `NOTION_API_KEY` | Notion API key |

### Allowlist (src/allowlist.json)

Slack 채널 및 Notion 리소스 접근 제어를 위한 설정 파일입니다.

```json
{
  "slack_channels": [
    {"channel_id": "C0123456789", "channel_name": "growth-data", "description": "..."}
  ],
  "notion_databases": [
    {"database_id": "abc123", "database_name": "Experiments", "description": "..."}
  ],
  "notion_pages": [
    {"page_id": "page123", "page_name": "Growth Playbook", "description": "..."}
  ]
}
```

> **Note**: `src/allowlist.json`은 `.gitignore`에 포함되어 있습니다. `src/allowlist.example.json`을 참고하세요.

## Development

### Adding a New Entity

1. `domain/entities/xxx.py` - Entity with `create()` factory
2. `domain/ports/xxx.py` - Repository ABC
3. `adapters/mongodb/collections/xxx_adapter.py` - Collection adapter
4. `adapters/repositories/mongodb/xxx.py` - Repository impl

### Adding a New Agent Tool

1. `adapters/agent/tools/xxx_tool.py` - @tool decorator
2. `adapters/agent/mcp_server.py` - MCP server 등록
3. `adapters/agent/tools/__init__.py` - GROWTH_TOOLS 추가

### Adding a New API Endpoint

1. `entrypoints/api/schemas/xxx.py` - Schemas
2. `entrypoints/api/routes/xxx.py` - Route handlers
3. `entrypoints/api/routes/__init__.py` - Router 등록

## License

MIT License
