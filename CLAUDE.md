# Agent Vision Project Context

**Growth Hacking Agent Backend - DDD + Hexagonal Architecture**

---

## Project Overview

Agent Vision은 Growth Hacking을 위한 대화형 AI 에이전트 백엔드 시스템입니다.
DDD + Hexagonal Architecture 패턴을 따릅니다.

**기술 스택**: Python 3.9+ | FastAPI | MongoDB (Motor) | Claude Agent SDK | OpenAI Embeddings | AWS SQS

**핵심 기능**:
- Conversational Agent: 연속 대화 기반 Growth 분석 (Async Worker 처리)
- Growth Memory: Vector Search 기반 RAG
- External Tools: Slack, Notion, EventLog

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
├── domain/              # Pure Python (no external dependencies)
│   ├── entities/
│   │   ├── agent_session.py    # Session entity
│   │   ├── message.py          # Conversation message entity
│   │   └── growth_memory.py    # Growth memory entity (embeddings)
│   ├── ports/           # Repository interfaces
│   │   ├── agent_session.py
│   │   ├── message.py
│   │   └── growth_memory.py
│   ├── value_objects/
│   │   ├── agent_enums.py      # SessionStatus, MessageRole, GrowthMemoryType
│   │   └── agent_types.py      # ToolCallVO, AgentResponse, etc.
│   └── exceptions.py    # Domain exceptions
├── service_layer/
│   └── application/
│       └── agent_orchestration_service.py  # enqueue_message + execute_agent_response
├── adapters/
│   ├── agent/           # Claude Agent SDK integration
│   │   ├── client.py        # GrowthAgentClient wrapper
│   │   ├── options.py       # Agent options configuration
│   │   ├── mcp_server.py    # MCP server with tools
│   │   ├── hooks/           # Agent lifecycle hooks
│   │   │   ├── pre_tool_use.py     # Allowlist validation
│   │   │   ├── post_tool_use.py    # Audit logging
│   │   │   └── session_hooks.py    # Session end handling
│   │   └── tools/           # Custom MCP tools
│   │       ├── eventlog_tool.py
│   │       ├── slack_tool.py
│   │       ├── notion_tool.py
│   │       └── growth_memory_tool.py
│   ├── mongodb/         # MongoDB client, collections, adapters
│   ├── repositories/    # Repository implementations
│   ├── aws/             # SQS producer/consumer
│   ├── openai/          # Embedding client
│   ├── external/        # Slack, Notion API clients
│   └── uow/             # Unit of Work implementation
├── entrypoints/
│   ├── api/             # FastAPI
│   │   ├── app.py           # Lifespan, middleware, routes
│   │   ├── routes/agent.py  # Agent session endpoints
│   │   └── schemas/agent.py # Request/Response schemas
│   ├── worker/          # SQS Worker
│   │   ├── app.py           # Worker entry point
│   │   ├── dependencies.py  # Worker dependencies (db, embedding)
│   │   └── tasks/
│   │       └── agent_tasks.py  # @task process_agent_response
│   └── cli/             # CLI Jobs
└── __about__.py

tests/
├── integration/
└── e2e/
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
│  1. Load session and messages                                   │
│  2. Build conversation context                                  │
│  3. Execute GrowthAgentClient (Claude Agent SDK)               │
│  4. Save assistant message to DB                                │
│  5. Set status → ACTIVE                                         │
└─────────────────────────────────────────────────────────────────┘
```

### Service Methods

```python
# API용 - 빠른 응답
async def enqueue_message(session_id, content, sqs_producer) -> Dict:
    # Save message + Set PROCESSING + Enqueue to SQS
    return {"status": "processing", "user_message_id": "..."}

# Worker용 - 무거운 작업
async def execute_agent_response(session_id, user_message_id) -> None:
    # Execute agent + Save response + Set ACTIVE
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
    sdk_session_id: Optional[str] = None  # Claude SDK session ID
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
    app.state.openai_client = OpenAIEmbeddingClient(...)
    app.state.sqs_producer = SQSProducerAdapter(...)  # For async processing
    _initialize_agent_tool_dependencies(app)
    yield
    app.state.db_client.close()
```

### 7. Task Registry Pattern
```python
# entrypoints/worker/tasks/agent_tasks.py
@task
async def process_agent_response(data: Dict[str, Any]) -> None:
    db_client = WorkerDependencies.get_db_client()
    embedding_client = WorkerDependencies.get_embedding_client()
    service = AgentOrchestrationService(db_client, embedding_client)
    await service.execute_agent_response(
        session_id=data["session_id"],
        user_message_id=data["user_message_id"]
    )
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
OPENAI_API_KEY=sk-xxx

# External (Optional)
SLACK_BOT_TOKEN=xoxb-xxx
NOTION_API_KEY=secret_xxx

# Allowlist (JSON arrays, integrated into Config)
SLACK_CHANNEL_ALLOWLIST='[{"channel_id": "C123", "channel_name": "growth-data"}]'
NOTION_DATABASE_ALLOWLIST='[{"database_id": "db123", "database_name": "Experiments"}]'
NOTION_PAGE_ALLOWLIST='[{"page_id": "page123", "page_name": "Growth Playbook"}]'

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

### New Agent Tool
1. `adapters/agent/tools/xxx_tool.py` - @tool 함수
2. `adapters/agent/mcp_server.py` - MCP 서버 등록
3. `adapters/agent/tools/__init__.py` - GROWTH_TOOLS 추가

---

## Agent System Architecture

### GrowthAgentClient Flow

```
┌──────────────────────────────────────────────────────┐
│              AgentOrchestrationService               │
│  execute_agent_response()                            │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                 GrowthAgentClient                    │
│  (Claude Agent SDK wrapper)                          │
├──────────────────────────────────────────────────────┤
│  PreToolUse:   Allowlist validation                  │
│  PostToolUse:  Audit logging                         │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│                 MCP Server (Tools)                   │
├──────────────────────────────────────────────────────┤
│  EventLog:      funnel_analysis, retention_analysis  │
│  Slack:         list_channels, get_messages          │
│  Notion:        list_resources, query_database       │
│  GrowthMemory:  search_memory, get_recent            │
└──────────────────────────────────────────────────────┘
```

### SDK Session Synchronization

```
[First Message]
session.sdk_session_id = None
GrowthAgentClient(resume_session_id=None) → new SDK session
Save sdk_session_id to database

[Subsequent Messages]
GrowthAgentClient(resume_session_id="sdk-xxx") → resumes SDK session
SDK maintains conversation context

[SDK Session Expired]
SDKSessionExpiredError → archive system session
Return error: "Session expired, create new session"
```

---

## Testing

```bash
pytest                          # All tests
pytest tests/integration/ -v    # Integration (requires MongoDB)
pytest tests/e2e/ -v            # E2E tests
pytest --cov=src               # Coverage
```
