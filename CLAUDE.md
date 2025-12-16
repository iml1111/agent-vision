# Agent Vision Project Context

**Growth Hacking Agent Backend - DDD + Hexagonal Architecture**

---

## Project Overview

Agent Vision은 Growth Hacking을 위한 AI 에이전트 백엔드 시스템입니다.
VOID 보일러플레이트 기반 DDD + Hexagonal Architecture 패턴을 따릅니다.

**기술 스택**: Python 3.9+ | FastAPI | MongoDB (Motor + Atlas Vector Search) | Claude Agent SDK | OpenAI Embeddings

**핵심 기능**:
- Agent Orchestration: Plan→Act→Observe→Critique→Decide 루프
- HITL (Human-in-the-Loop): 중요 의사결정시 인간 개입
- Growth Memory: Vector Search 기반 RAG 시스템
- External Tool Integration: Slack, Notion, EventLog 연동

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
├── config/              # Configuration modules
│   └── allowlist.py     # Slack/Notion allowlist configuration
├── domain/              # Pure Python (no external dependencies)
│   ├── entities/        # Domain entities with identity-based equality
│   │   ├── agent_session.py    # Agent session entity
│   │   ├── agent_loop.py       # Agent loop entity
│   │   ├── observation.py      # Observation entity
│   │   └── growth_memory.py    # Growth memory entity (with embeddings)
│   ├── ports/           # Abstract interfaces (repositories)
│   └── value_objects/   # Enums and value objects
│       └── agent_enums.py      # SessionStatus, LoopPhase, DecisionType, etc.
├── service_layer/       # Use Cases
│   └── application/
│       ├── agent_orchestration_service.py  # Main agent loop orchestration
│       ├── observation_service.py          # Tool result/error recording
│       └── growth_memory_service.py        # RAG memory management
├── adapters/            # Infrastructure implementations
│   ├── openai/          # OpenAI embedding client
│   ├── external/        # Slack, Notion API clients
│   ├── agent/           # Claude Agent SDK integration
│   │   ├── mcp_server.py    # MCP server with tools
│   │   ├── options.py       # Agent options configuration
│   │   └── client.py        # GrowthAgentClient wrapper
│   ├── agent_tools/     # Custom MCP tools
│   │   ├── eventlog_tool.py     # MongoDB analytics queries
│   │   ├── slack_tool.py        # Slack channel access
│   │   ├── notion_tool.py       # Notion database access
│   │   └── growth_memory_tool.py # Vector search RAG
│   ├── agent_hooks/     # Agent lifecycle hooks
│   │   ├── pre_tool_use.py     # Allowlist validation
│   │   ├── post_tool_use.py    # Observation capture
│   │   └── session_hooks.py    # Session end handling
│   ├── mongodb/         # MongoDB client, collections, adapters
│   ├── repositories/    # Repository implementations
│   └── uow/             # Unit of Work implementation
├── entrypoints/         # Application entry points
│   ├── api/             # FastAPI
│   │   ├── routes/agent.py     # Agent session API endpoints
│   │   └── schemas/agent.py    # Request/Response schemas
│   ├── worker/          # SQS Worker
│   └── cli/             # CLI Jobs
├── config.py            # Pydantic BaseSettings
└── __about__.py         # Version info

tests/
├── integration/         # Repository & service integration tests
└── e2e/                 # API endpoint tests
```

---

## Key Design Patterns

### 1. Async/Await Pattern
**전체 프로젝트에서 async/await 일관 사용**

```python
# Repository Layer
async def create(self, entity: ItemEntity) -> str:
    doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
    result = await self._adapter.insert_one(doc)
    return str(result.inserted_id)

# Service Layer (단일 read: 직접 repository 호출)
async def get_item(self, item_id: str) -> ItemEntity:
    item = await self._item_repo.get_by_id(item_id)
    if not item:
        raise ItemNotFoundError(f"Item {item_id} not found")
    return item
```

---

### 2. BaseEntity Pattern
**요구사항**: `@dataclass(eq=False, frozen=True)`, `from_dict()`, `validate()`, Identity-based equality

```python
@dataclass(eq=False, frozen=True)
class ItemEntity(BaseEntity):
    name: str
    description: str
    status: ItemStatus
    created_at: datetime
    id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def create(cls, name: str, ...) -> "ItemEntity":
        """Factory method for new entity creation"""
        return cls(name=name, created_at=datetime.now(timezone.utc), ...)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ItemEntity":
        # _id → id conversion, field filtering
        ...

    def validate(self) -> None:
        if not self.name.strip():
            raise ValueError("Item name is required")

    def __eq__(self, other): return self.id == other.id
    def __hash__(self): return hash(self.id)
```

---

### 3. Repository Pattern
**구조**: ABC Interface (Port) → MongoDB Implementation (Adapter)

```python
# Port (domain/ports/item.py)
class ItemRepository(ABC):
    @abstractmethod
    async def create(self, entity: ItemEntity) -> str: ...

    @abstractmethod
    async def get_by_id(self, item_id: str) -> Optional[ItemEntity]: ...

# Adapter (adapters/repositories/mongodb/item.py)
class MongoItemRepository(ItemRepository):
    async def create(self, entity: ItemEntity) -> str:
        doc = BaseMongoAdapter.prepare_for_insert(entity.to_dict())
        result = await self._adapter.insert_one(doc)
        return str(result.inserted_id)
```

---

### 4. Unit of Work (UoW) Pattern
**목적**: 다중 write 작업의 원자성 보장

**원칙**:
- ✅ 2+ write가 원자적 처리 필요 시만 사용
- ❌ 단일 read/write는 직접 repository 호출

```python
# 다중 write: UoW
async with MongoUnitOfWork(db_client) as uow:
    await uow.item_repo.create(entity1)
    await uow.item_repo.create(entity2)
    await uow.commit()

# 단일 read: 직접 호출
item = await self._item_repo.get_by_id(item_id)
```

**요구사항**: MongoDB Replica Set (트랜잭션 지원)

---

### 5. Exception Pattern
**Domain 예외는 순수 Python, 각 API Route에서 HTTPException으로 변환**

```python
# domain/exceptions.py - 순수 Python (HTTP 개념 없음)
class DomainError(Exception):
    """Base exception for all domain errors"""
    pass

class EntityNotFoundError(DomainError):
    """Entity with given ID does not exist"""
    pass

class ItemNotFoundError(EntityNotFoundError):
    """Item with given ID does not exist"""
    pass

class ItemValidationError(DomainError):
    """Item data validation failed"""
    pass

# API Route - try-except + HTTPException 변환
@router.get("/{item_id}")
async def get_item(item_id: str, service = Depends(get_item_service)):
    try:
        item = await service.get_item(item_id)
    except ItemNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return ItemResponse(...)

# 5XX 에러는 @app.exception_handler(Exception)이 자동 처리
```

---

### 6. Lifespan Singleton Pattern
**목적**: 무거운 리소스(DB 커넥션 풀)를 앱 시작 시 1회 초기화

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize singletons
    app.state.db_client = MongoDBClient(uri=config.mongodb_uri, ...)
    yield
    # Shutdown: Cleanup
    app.state.db_client.close()
```

---

### 7. Task/Job Registry Pattern
**Worker**: `@task` 데코레이터로 SQS 메시지 핸들러 등록
**CLI**: `@job` 데코레이터로 cronjob/background job 등록

```python
# Worker task (Write 예시)
@task
async def process_item(data: Dict[str, Any]) -> None:
    service = ItemService(db_client)
    await service.create_item(name=data["name"], ...)

# CLI job (Read 예시)
@job
async def process_item(item_id: str) -> None:
    service = ItemService(db_client)
    item = await service.get_item(item_id)
```

---

## Entrypoints

### API (FastAPI)
```bash
./void run api  # uvicorn with --reload
```

**구조**: `app.py` → `lifespan` → `middleware` → `exception_handlers` → `routes`

### Worker (SQS Consumer)
```bash
./void run worker
```

**구조**: `app.py` → `dependencies.initialize()` → `register_all_tasks()` → `consumer.start()`

### CLI (Click)
```bash
./void run job <JOB_NAME>
./void run job process_item --item-id 507f1f77bcf86cd799439011
```

**구조**: `app.py` → `dependencies.initialize()` → `register_all_jobs()` → `handler.execute()`

---

## Current API Endpoints

### Core Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/items` | Create item |
| GET | `/api/v1/items/{id}` | Get item by ID |

### Agent Endpoints
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/agent/sessions` | Create agent session |
| POST | `/api/v1/agent/sessions/{id}/messages` | Send message (start/continue processing) |
| GET | `/api/v1/agent/sessions/{id}/status` | Poll session status |
| GET | `/api/v1/agent/sessions/{id}/observations` | Get session observations |
| POST | `/api/v1/agent/sessions/{id}/hitl` | Submit HITL response |
| DELETE | `/api/v1/agent/sessions/{id}` | Cancel session |

### Agent Session Status Flow
```
[created] → POST /messages → [processing] → GET /status (poll)
                                   ↓
            [waiting_hitl] ← needs HITL → POST /hitl → [processing]
                                   ↓
                            [completed] → final_decision in response
```

---

## Configuration

환경변수는 `.env` 파일 또는 시스템 환경변수로 설정:

```bash
# MongoDB
MONGODB_URI=mongodb://localhost:27017
MONGODB_NAME=agent_vision

# AI/LLM
ANTHROPIC_API_KEY=sk-ant-xxx
OPENAI_API_KEY=sk-xxx

# External Integrations (Optional)
SLACK_BOT_TOKEN=xoxb-xxx
NOTION_API_KEY=secret_xxx

# Agent Configuration
AGENT_MAX_LOOP_COUNT=10
AGENT_HITL_TIMEOUT_SECONDS=3600

# Allowlist (JSON arrays)
SLACK_CHANNEL_ALLOWLIST='[{"channel_id": "C123", "channel_name": "growth-data"}]'
NOTION_DATABASE_ALLOWLIST='[{"database_id": "db123", "database_name": "Experiments"}]'
NOTION_PAGE_ALLOWLIST='[{"page_id": "page123", "page_title": "Growth Playbook"}]'

# AWS (Optional)
AWS_ACCESS_KEY_ID=xxx
AWS_SECRET_ACCESS_KEY=xxx
AWS_REGION=ap-northeast-2
SQS_QUEUE_URL=https://sqs.ap-northeast-2.amazonaws.com/xxx/queue.fifo
```

---

## Adding New Features

### New Entity
1. `domain/entities/xxx.py` - Entity 정의 (`create()` factory method 포함)
2. `domain/ports/xxx.py` - Repository ABC 정의
3. `domain/value_objects/xxx_enums.py` - Enum 정의 (필요시)
4. `adapters/mongodb/collections/xxx_adapter.py` - Collection adapter
5. `adapters/repositories/mongodb/xxx.py` - Repository 구현
6. `adapters/uow/mongo_unit_of_work.py` - UoW에 repository 추가

### New API Endpoint
1. `entrypoints/api/schemas/xxx.py` - Request/Response schemas
2. `entrypoints/api/routes/xxx.py` - Route handlers
3. `entrypoints/api/routes/__init__.py` - Router 등록
4. `entrypoints/api/dependencies/services.py` - Service dependency 추가

### New Worker Task
1. `entrypoints/worker/tasks/xxx.py` - @task 데코레이터로 핸들러 정의
2. `entrypoints/worker/tasks/__init__.py` - TASK_MODULES에 추가

### New CLI Job
1. `entrypoints/cli/jobs/xxx.py` - @job 데코레이터로 핸들러 정의
2. `entrypoints/cli/jobs/__init__.py` - JOB_MODULES에 추가

### New Exception
1. `domain/exceptions.py` - `DomainError` 또는 적절한 기본 예외 상속
2. `domain/__init__.py` - 예외 export 추가
3. API Route에서 `try-except` + `HTTPException` 변환

### New Agent Tool
1. `adapters/agent_tools/xxx_tool.py` - `@tool` 데코레이터로 함수 정의
2. `adapters/agent/mcp_server.py` - MCP 서버에 tool 등록
3. `adapters/agent/options.py` - `GROWTH_TOOL_NAMES`에 tool 이름 추가

---

## Agent System Architecture

### Agent Loop (Plan→Act→Observe→Critique→Decide)

```
┌─────────────────────────────────────────────────────────┐
│                   AgentOrchestrationService             │
├─────────────────────────────────────────────────────────┤
│  Session Creation → Loop Execution → Decision Output    │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    GrowthAgentClient                    │
│  (Claude Agent SDK wrapper with hooks & tools)          │
├─────────────────────────────────────────────────────────┤
│  PreToolUse Hooks:    Allowlist validation              │
│  PostToolUse Hooks:   Observation capture               │
│  Session Hooks:       Memory summarization              │
└───────────────────────────┬─────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────┐
│                    MCP Server (Tools)                   │
├─────────────────────────────────────────────────────────┤
│  EventLog:       funnel_analysis, retention_analysis    │
│  Slack:          list_channels, get_messages            │
│  Notion:         list_resources, query_database         │
│  GrowthMemory:   search_memory, get_recent              │
└─────────────────────────────────────────────────────────┘
```

### Decision Types

| Type | Description | Session State |
|------|-------------|---------------|
| `CONTINUE` | Need more information | PROCESSING |
| `HITL_QUESTION` | Request human input | WAITING_HITL |
| `EXPERIMENT` | Recommend A/B test | COMPLETED |
| `INSTRUMENTATION_TODO` | Need event tracking | COMPLETED |

### Growth Memory (RAG)

```python
# Vector search for relevant context
memories = await memory_service.search_relevant_memories(
    query="user retention mobile",
    limit=5
)

# Session summarization to long-term memory
await memory_service.distill_session_to_memory(session_id)
```

### Allowlist Enforcement

Server-side blocking via PreToolUse hooks:
- Slack: Only whitelisted channel IDs
- Notion: Only whitelisted database/page IDs
- Violations raise `AllowlistViolationError`

---

## Testing

```bash
# Run all tests
pytest

# Run integration tests (requires MongoDB)
pytest tests/integration/ -v

# Run E2E tests
pytest tests/e2e/ -v

# Run with coverage
pytest --cov=src --cov-report=html
```
