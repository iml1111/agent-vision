# Agent Vision Project Context

**Growth Hacking Agent Backend - DDD + Hexagonal Architecture**

---

## Project Overview

Agent Vision은 Growth Hacking을 위한 대화형 AI 에이전트 백엔드 시스템입니다.
DDD + Hexagonal Architecture 패턴을 따릅니다.

**기술 스택**: Python 3.9+ | FastAPI | MongoDB (Motor) | Claude Agent SDK | AWS SQS

**핵심 기능**:
- Conversational Agent: 연속 대화 기반 Growth 분석 (Async Worker 처리)
- External Tools: Slack, Notion, EventLog
- GrowthMemory: 세션 아카이브 시 RAG 기반 장기 메모리 저장 (Atlas Vector Search)

---

## Architecture Principles

### 1. Domain-Driven Design (DDD)
- **Domain Layer**: 순수 Python, 외부 의존성 없음
- **Service Layer**: Use Case 구현, Domain-Infrastructure 조율
- **Infrastructure Layer**: 외부 시스템 통합 (DB, API)

### 2. Hexagonal Pattern
- **Port**: Interface (추상화) - `domain/ports/`
- **Adapter**: 구현체 (기술 스택) - `adapters/`
- Domain → Port 의존, Adapter는 Domain 독립

### 3. Identity-Based Equality
Entity는 ID로 식별 (`__eq__`, `__hash__`), Set/Dict 키로 사용 가능

---

## Directory Structure

```
src/
├── config.py            # Pydantic BaseSettings (Allowlist 포함)
├── logging_config.py    # Python 표준 logging 설정 (setup_logging, get_logger)
├── domain/              # Pure Python (no external dependencies)
│   ├── entities/
│   │   ├── agent_session.py    # Session entity
│   │   ├── message.py          # Conversation message entity
│   │   └── growth_memory.py    # GrowthMemory entity (6개 요약 단위)
│   ├── ports/           # Repository interfaces
│   │   ├── agent_session.py
│   │   ├── message.py
│   │   └── growth_memory.py    # vector_search 포함
│   ├── value_objects/
│   │   ├── agent_enums.py      # SessionStatus, MessageRole
│   │   └── agent_types.py      # ToolCallVO, AgentStreamEvent, GrowthMemorySummaryVO
│   └── exceptions.py    # Domain exceptions (SummarizationError 포함)
├── service_layer/
│   └── application/
│       ├── session_management_service.py   # Session CRUD
│       ├── agent_orchestration_service.py  # Message processing + Agent execution
│       └── growth_memory_service.py        # GrowthMemory 생성/검색
├── adapters/
│   ├── agent/           # Claude Agent SDK integration
│   │   ├── client.py        # GrowthAgentClient wrapper (MCP server 인라인 생성)
│   │   ├── options.py       # Agent options configuration
│   │   └── tools/           # Custom MCP tools
│   │       ├── eventlog_tool.py
│   │       ├── slack_tool.py
│   │       ├── notion_tool.py
│   │       └── growth_memory_tool.py  # RAG 검색 도구
│   ├── anthropic/       # Claude API clients
│   │   └── summarization_client.py  # Session 요약 (6가지 단위)
│   ├── mongodb/         # MongoDB client, collections, adapters
│   │   └── collections/
│   │       ├── eventlog_adapter.py       # EventLog aggregation (analytics tools)
│   │       └── growth_memory_adapter.py  # $vectorSearch 지원
│   ├── repositories/    # Repository implementations
│   │   └── mongodb/
│   │       └── growth_memory.py  # vector_search 구현
│   ├── aws/             # SQS producer/consumer
│   ├── openai/          # OpenAI embedding client (text-embedding-3-small)
│   ├── external/        # Slack, Notion API clients
│   └── uow/             # Unit of Work implementation
├── entrypoints/
│   ├── api/             # FastAPI
│   │   ├── app.py           # Lifespan, middleware, routes
│   │   ├── routes/agent.py  # Agent session endpoints
│   │   └── schemas/agent.py # Request/Response schemas
│   ├── worker/          # SQS Worker
│   │   ├── app.py           # Worker entry point
│   │   ├── dependencies.py  # Worker dependencies (db, sqs_producer, summarization)
│   │   └── tasks/
│   │       ├── agent_tasks.py   # @task process_agent_response
│   │       └── memory_tasks.py  # @task archive_session_to_memory
│   └── cli/             # CLI Jobs
└── __about__.py

scripts/
├── agent_chat.py        # POC CLI for API testing
├── archive_session.py   # Archive session + SQS enqueue (--skip-memory 옵션)
└── insert_sample_growth_memory.py  # GrowthMemory 샘플 문서 삽입
```

---

## Async Worker Pattern (SQS)

API는 빠른 응답을 위해 메시지만 저장 후 SQS에 enqueue. Worker가 실제 Agent 실행.

```
┌─────────────────────────────────────────────────────────────────┐
│                           API Layer                             │
├─────────────────────────────────────────────────────────────────┤
│  POST /messages                                                 │
│  1. Validate session state                                      │
│  2. Save user message to DB                                     │
│  3. Set status → PROCESSING                                     │
│  4. Enqueue to SQS (message_group_id=session_id)               │
│  5. Return {status: "processing", user_message_id: "..."}      │
└────────────────────────────┬────────────────────────────────────┘
                             │ SQS FIFO Queue
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                         Worker Layer                            │
├─────────────────────────────────────────────────────────────────┤
│  @task process_agent_response(data)                             │
│  1. Load session and user message                               │
│  2. Execute GrowthAgentClient.stream_query()                    │
│  3. For each event (TEXT, TOOL_USE):                            │
│     → Save as individual MessageEntity to DB                    │
│  4. On COMPLETE: update claude_session_id if changed            │
│  5. Set status → ACTIVE                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Service Layer

```python
# SessionManagementService - Session CRUD
class SessionManagementService:
    def __init__(self, db_client): ...
    async def create_session() -> AgentSessionEntity
    async def get_session(session_id) -> AgentSessionEntity
    async def get_session_status(session_id) -> SessionStatusVO
    async def get_messages(session_id, limit, offset) -> List[MessageEntity]
    async def archive_session(session_id) -> bool
    async def delete_session(session_id) -> bool

# AgentOrchestrationService - Message processing + Agent execution
class AgentOrchestrationService:
    def __init__(self, db_client, eventlog_adapter, slack_client, notion_client, config,
                 memory_repo, embedding_client): ...
    async def enqueue_message(session_id, content, sqs_producer) -> MessageEnqueueResultVO
    async def execute_agent_response(session_id, user_message_id, sqs_producer=None) -> None
    # Tool dependencies (including RAG) are passed to GrowthAgentClient
```

---

## Key Design Patterns

### 1. Async/Await Pattern
```python
async def create(self, entity: AgentSessionEntity) -> str:
    doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
    result = await self._adapter.insert_one(doc)
    return str(result.inserted_id)
```

### 2. BaseEntity Pattern
```python
@dataclass(eq=False, frozen=True)
class AgentSessionEntity(BaseEntity):
    status: SessionStatus
    created_at: datetime
    id: Optional[str] = None
    claude_session_id: Optional[str] = None  # Claude SDK session ID
    updated_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None

    @classmethod
    def create(cls) -> "AgentSessionEntity":
        return cls(status=SessionStatus.ACTIVE, created_at=datetime.now(timezone.utc))

    def __eq__(self, other): return self.id == other.id
    def __hash__(self): return hash(self.id)
```

### 3. Repository Pattern
```python
# Port (domain/ports/agent_session.py)
class AgentSessionRepository(ABC):
    @abstractmethod
    async def create(self, entity) -> str: ...
    @abstractmethod
    async def get_by_id(self, session_id) -> Optional[AgentSessionEntity]: ...

# Adapter (adapters/repositories/mongodb/agent_session.py)
class MongoAgentSessionRepository(AgentSessionRepository):
    async def create(self, entity):
        doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
        result = await self._adapter.insert_one(doc)
        return str(result.inserted_id)
```

### 4. Unit of Work (UoW) Pattern
2+ write가 원자적 처리 필요 시만 사용. 단일 read/write는 직접 repository 호출.

```python
async with MongoUnitOfWork(db_client) as uow:
    await uow.session_repo.create(session_entity)
    await uow.message_repo.create(message_entity)
    await uow.commit()
```

### 5. Exception Pattern
Domain 예외는 순수 Python, API Route에서 HTTPException으로 변환.

```python
# domain/exceptions.py
class AgentSessionNotFoundError(EntityNotFoundError): pass
class InvalidSessionStateError(DomainError): pass
class SDKSessionExpiredError(DomainError): pass

# API Route
try:
    result = await service.enqueue_message(...)
except AgentSessionNotFoundError as e:
    raise HTTPException(status_code=404, detail=str(e))
except InvalidSessionStateError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

### 6. Lifespan Singleton Pattern
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_client = MongoDBClient(...)
    app.state.sqs_producer = SQSProducerAdapter(...)
    app.state.slack_client = SlackClient(...) if token else None
    app.state.notion_client = NotionClient(...) if key else None
    yield
    app.state.db_client.close()
```

### 7. Task Registry Pattern
```python
# entrypoints/worker/tasks/agent_tasks.py
@task
async def process_agent_response(data: Dict[str, Any]) -> None:
    db_client = WorkerDependencies.get_db_client()
    sqs_producer = WorkerDependencies.get_sqs_producer()
    config = WorkerDependencies.get_config()
    eventlog_adapter = WorkerDependencies.get_eventlog_adapter()
    slack_client = WorkerDependencies.get_slack_client()
    notion_client = WorkerDependencies.get_notion_client()
    memory_repo = WorkerDependencies.get_memory_repo()
    embedding_client = WorkerDependencies.get_embedding_client()

    service = AgentOrchestrationService(
        db_client=db_client,
        eventlog_adapter=eventlog_adapter,
        slack_client=slack_client,
        notion_client=notion_client,
        config=config,
        memory_repo=memory_repo,
        embedding_client=embedding_client,
    )
    await service.execute_agent_response(...)

# entrypoints/worker/tasks/memory_tasks.py
@task
async def archive_session_to_memory(data: Dict[str, Any]) -> None:
    """세션 아카이브 → GrowthMemory 생성 (요약 + 임베딩)"""
    session_id = data["session_id"]
    service = GrowthMemoryService(db_client, summarization_client, embedding_client)
    await service.create_memory_from_session(session_id)
```

---

## Entrypoints

### API (FastAPI)
```bash
./void run api  # uvicorn with --reload
```

### Worker (SQS Consumer)
```bash
./void run worker
```

### CLI (Click)
```bash
./void run job <JOB_NAME>
```

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/agent/sessions` | Create session |
| POST | `/api/v1/agent/sessions/{id}/messages` | Send message (async, returns immediately) |
| GET | `/api/v1/agent/sessions/{id}/messages` | Get conversation history |
| GET | `/api/v1/agent/sessions/{id}/status` | Get session status (poll for completion) |
| DELETE | `/api/v1/agent/sessions/{id}` | Delete session |

### Client Usage Flow

```
1. POST /sessions → {"session_id": "...", "status": "active"}

2. POST /sessions/{id}/messages
   Body: {"content": "분석해줘"}
   Response: {"status": "processing", "user_message_id": "..."}

3. GET /sessions/{id}/status (polling)
   Response: {"status": "processing"} or {"status": "active"}

4. GET /sessions/{id}/messages (when status=active)
   Response: [user_message, assistant_message]
```

### Session Status Flow

```
POST /sessions → [active]
       ↓
POST /messages → [processing] → Worker completes → [active]
       ↓
SDK Session Expired → [archived] (automatic)
       ↓
DELETE → permanently removed
```

### Session Status Values
| Status | Description |
|--------|-------------|
| `active` | 대화 진행 중 (기본 상태) |
| `processing` | Worker에서 응답 생성 중 (사용자 입력 불가) |
| `archived` | SDK 세션 만료로 보관됨 (재활성화 불가) |

---

## Configuration

```bash
# Core
MONGODB_URI=mongodb://localhost:27017
MONGODB_NAME=agent_vision
ANTHROPIC_API_KEY=sk-ant-xxx
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# External Tools
SLACK_BOT_TOKEN=xoxb-xxx
NOTION_API_KEY=secret_xxx
OPENAI_API_KEY=sk-xxx  # For embeddings

# Notion EventLog Spec DB (for get_eventlog_specs tool)
NOTION_EVENTLOG_SPEC_DB_ID=your-eventlog-spec-db-id

# Allowlist (JSON file: src/allowlist.json)
# - slack_channels: [{channel_id, channel_name, description}]
# - notion_pages: [{page_id, page_name, description}]

# AWS SQS (Required for async processing)
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=ap-northeast-2
SQS_QUEUE_URL=https://sqs.ap-northeast-2.amazonaws.com/xxx/queue.fifo
```

---

## Adding New Features

### New Entity
1. `domain/entities/xxx.py` - Entity with `create()` factory
2. `domain/ports/xxx.py` - Repository ABC
3. `adapters/mongodb/collections/xxx_adapter.py` - Collection adapter
4. `adapters/repositories/mongodb/xxx.py` - Repository impl

### New API Endpoint
1. `entrypoints/api/schemas/xxx.py` - Schemas
2. `entrypoints/api/routes/xxx.py` - Route handlers
3. `entrypoints/api/routes/__init__.py` - Router 등록

### New Worker Task
1. `entrypoints/worker/tasks/xxx.py` - @task 핸들러
2. `entrypoints/worker/tasks/__init__.py` - TASK_MODULES 추가

### New Agent Tool (Factory Pattern)
1. `adapters/agent/tools/xxx_tool.py` - `create_xxx_tools(dependencies)` 팩토리 함수
2. `adapters/agent/tools/__init__.py` - 팩토리 함수 export 추가
3. `adapters/agent/client.py` - `GrowthAgentClient.__init__`에서 팩토리 호출
4. `entrypoints/worker/dependencies.py` - 필요시 의존성 추가

---

## Agent System Architecture

### Tool Factory Pattern (Dependency Injection)

Agent Tools는 팩토리 함수 패턴으로 의존성 주입:

```python
# adapters/agent/tools/eventlog_tool.py
def create_eventlog_tools(eventlog_adapter) -> List:
    @tool("run_eventlog_aggregation", ...)
    async def run_eventlog_aggregation(args): ...
    return [run_eventlog_aggregation]

# adapters/agent/client.py
class GrowthAgentClient:
    def __init__(self, eventlog_adapter, slack_client, notion_client, config,
                 memory_repo, embedding_client, message_repo,
                 model="claude-opus-4-5", resume_session_id=None):
        tools = []
        tools.extend(create_eventlog_tools(eventlog_adapter))
        tools.extend(create_slack_tools(slack_client, config))
        tools.extend(create_notion_tools(notion_client, config))
        tools.extend(create_growth_memory_tools(memory_repo, embedding_client, message_repo))
        self._mcp_server = create_sdk_mcp_server(tools=tools)
```

### GrowthAgentClient Flow

```
┌──────────────────────────────────────────────────────┐
│              AgentOrchestrationService               │
│  execute_agent_response(session_id, user_message_id) │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                 GrowthAgentClient                    │
│  (Claude Agent SDK wrapper with DI + session resume) │
├──────────────────────────────────────────────────────┤
│  __init__(eventlog_adapter, slack_client,            │
│           notion_client, config, memory_repo,        │
│           embedding_client, message_repo)            │
│  → create_*_tools() factories build MCP tools        │
├──────────────────────────────────────────────────────┤
│  stream_query() → yields AgentStreamEvent            │
│  - TEXT: text content from assistant                 │
│  - TOOL_USE: tool call with id, name, input          │
│  - COMPLETE: final event with claude_session_id      │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                 MCP Server (Tools)                   │
├──────────────────────────────────────────────────────┤
│  EventLog:      run_eventlog_aggregation             │
│                 (MongoDB pipeline 직접 실행)          │
│  Slack:         list_slack_channels, get_slack_messages │
│  Notion:        list_notion_pages, get_notion_page,  │
│                 get_eventlog_specs                   │
│  GrowthMemory:  search_growth_memory                 │
│                 (RAG 기반 유사 사례 검색)              │
│                 get_session_messages                 │
│                 (과거 세션 대화 기록 조회)             │
└──────────────────────────────────────────────────────┘
```

### SDK Session Resume Pattern

SDK가 conversation history를 자동 관리하므로, 매번 히스토리를 수동으로 전달할 필요 없음.

```
[First Message]
session.claude_session_id = None
GrowthAgentClient(resume_session_id=None) → new SDK session
Save claude_session_id to database

[Subsequent Messages]
GrowthAgentClient(resume_session_id="sdk-xxx")
→ SDK automatically resumes conversation context
→ Only new user message is passed to agent

[SDK Session Expired]
SDKSessionExpiredError → archive system session
Return error: "Session expired, create new session"
```

**Note**: 메시지는 DB에 저장되지만 이는 히스토리 조회용. Agent 실행 시에는 현재 user message만 전달.

### Streaming Event Storage Pattern

각 에이전트 응답 이벤트를 개별 메시지로 DB에 실시간 저장:

```python
async for event in client.stream_query(user_message.content):
    if event.type == AgentMessageType.TEXT:
        # 텍스트 응답 저장
        message = MessageEntity.create(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=event.content,
            metadata={"event_type": "text", "sequence": n}
        )
        await message_repo.create(message)

    elif event.type == AgentMessageType.TOOL_USE:
        # 도구 호출 저장
        message = MessageEntity.create(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=f"Tool: {event.tool_call.name}",
            metadata={
                "event_type": "tool_use",
                "sequence": n,
                "tool_call": {"id": ..., "name": ..., "input": ...}
            }
        )
        await message_repo.create(message)

    elif event.type == AgentMessageType.COMPLETE:
        # claude_session_id 업데이트 (변경 시)
        if event.claude_session_id != resume_session_id:
            await session_repo.update_claude_session_id(...)
```

**장점**: 긴 응답도 실시간 진행 상황 조회 가능, 중단 시 부분 결과 보존

---

## Scripts

### POC CLI (scripts/agent_chat.py)

API 테스트용 대화형 CLI:

```bash
# 새 세션으로 시작
python scripts/agent_chat.py

# 기존 세션 이어서
python scripts/agent_chat.py --session-id <id>

# 다른 서버로 연결
python scripts/agent_chat.py --base-url http://localhost:8080
```

**기능**: 세션 생성/선택 → 대화 루프 (1초 polling) → history 조회

---

## GrowthMemory System

세션 아카이브 시 대화 내용을 Claude API로 요약하여 장기 메모리로 저장. Atlas Vector Search로 유사 사례 검색 지원.

### Architecture Flow

```
[Archive Trigger]
├─ SDK Session Expired (자동) → AgentOrchestrationService._archive_session()
└─ Manual Archive (수동) → scripts/archive_session.py
         │
         ▼
[SQS Enqueue] task_type="archive_session_to_memory"
         │
         ▼
[Worker Task] archive_session_to_memory
├─1. Session/Messages 조회
├─2. Claude API 요약 (6가지 단위)
├─3. Embedding 생성 (Problem + Bottleneck)
└─4. GrowthMemory 저장 (idempotent)
         │
         ▼
[MongoDB Collection] GrowthMemory
- content_vector: 1536 dim (Atlas Vector Search)
```

### GrowthMemoryEntity 구조

```python
@dataclass(eq=False, frozen=True)
class GrowthMemoryEntity(BaseEntity):
    session_id: str
    created_at: datetime
    id: Optional[str] = None

    # 6가지 요약 단위
    problem_snapshot: Optional[str] = None      # 문제 정의
    bottleneck_evidence: Optional[str] = None   # 병목/근거
    hypotheses: Optional[List[str]] = None      # 가설 목록
    experiment_cards: Optional[List[Dict]] = None  # 실험 카드
    outcome: Optional[str] = None               # 결과
    learnings_next_actions: Optional[str] = None  # 학습/다음 액션

    # Vector Search
    content_vector: Optional[List[float]] = None  # 1536 dim
    vector_text: Optional[str] = None             # Problem + Bottleneck
```

### GrowthMemoryService

```python
class GrowthMemoryService:
    async def create_memory_from_session(session_id: str) -> str:
        """세션 아카이브 → 요약 → 임베딩 → 저장 (Worker task에서 호출)"""
```

### Atlas Vector Search Index (수동 생성 필요)

```json
{
  "name": "growth_memory_vector_index",
  "type": "vectorSearch",
  "definition": {
    "fields": [{
      "type": "vector",
      "path": "content_vector",
      "numDimensions": 1536,
      "similarity": "cosine"
    }]
  }
}
```

### Usage

```bash
# 수동 아카이브 (메모리 추출 포함)
python scripts/archive_session.py <session_id>

# 수동 아카이브 (메모리 추출 스킵)
python scripts/archive_session.py <session_id> --skip-memory
```

### GrowthMemory Tools

Agent가 과거 유사 사례를 검색하고 대화 기록을 조회할 수 있는 MCP 도구:

```python
# adapters/agent/tools/growth_memory_tool.py
def create_growth_memory_tools(memory_repo, embedding_client, message_repo) -> List:
    @tool("search_growth_memory", ...)
    async def search_growth_memory(args):
        # query 텍스트 → 임베딩 → Vector Search → 유사 메모리 반환
        ...

    @tool("get_session_messages", ...)
    async def get_session_messages(args):
        # session_id로 과거 대화 기록 조회
        messages = await message_repo.get_by_session_id(session_id, limit)
        return formatted_messages

    return [search_growth_memory, get_session_messages]
```

**Tool Specs**:

| Tool | Parameters | Description |
|------|------------|-------------|
| `search_growth_memory` | `query` (required), `limit` (optional, default: 3, max: 10) | Vector Search로 유사 사례 검색 |
| `get_session_messages` | `session_id` (required), `limit` (optional, default: 50, max: 100) | 과거 세션 대화 기록 조회 |

**사용 흐름**:
1. `search_growth_memory`로 유사 사례 검색 → `session_id` 반환
2. `get_session_messages`로 해당 세션의 실제 대화 기록 조회
