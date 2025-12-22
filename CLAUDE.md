# Agent Vision Project Context

**Growth Hacking Agent Backend - DDD + Hexagonal Architecture**

---

## Project Overview

Agent Vision은 Growth Hacking을 위한 대화형 AI 에이전트 백엔드 시스템입니다.
DDD + Hexagonal Architecture 패턴을 따릅니다.

**기술 스택**: Python 3.12+ | FastAPI | MongoDB (Motor) | Claude Agent SDK | AWS SQS

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
│   │   ├── growth_memory.py    # GrowthMemory entity (6개 요약 단위)
│   │   └── subagent_trace.py   # SubAgentTrace entity (디버깅/분석용)
│   ├── ports/           # Repository interfaces
│   │   ├── agent_session.py
│   │   ├── message.py
│   │   ├── growth_memory.py    # vector_search 포함
│   │   └── subagent_trace.py   # Sub-agent trace repository
│   ├── value_objects/
│   │   ├── agent_enums.py      # SessionStatus, MessageRole
│   │   └── agent_types.py      # ToolCallVO, AgentStreamEvent, SubAgentExecutionResult
│   └── exceptions.py    # Domain exceptions (SummarizationError 포함)
├── service_layer/
│   └── application/
│       ├── session_management_service.py   # Session CRUD
│       ├── agent_orchestration_service.py  # Message processing + Supervisor execution
│       └── growth_memory_service.py        # GrowthMemory 생성/검색
├── adapters/
│   ├── agent/           # Claude Agent SDK integration
│   │   ├── supervisor/      # Supervisor Agent (coordinates sub-agents)
│   │   │   ├── client.py        # SupervisorAgentClient
│   │   │   ├── options.py       # Supervisor options + system prompt
│   │   │   └── tools/
│   │   │       └── subagent_tools.py  # call_slack, call_product, call_data, call_memory
│   │   └── subagents/       # Specialized Sub-Agents
│   │       ├── base.py          # BaseSubAgent abstract class (+ built-in tools)
│   │       ├── slack.py         # SlackAgent
│   │       ├── product_domain.py  # ProductDomainAgent
│   │       ├── data_analysis.py   # DataAnalysisAgent
│   │       ├── memory.py        # MemoryAgent
│   │       └── tools/           # Custom MCP tools (used by sub-agents)
│   │           ├── eventlog_tool.py
│   │           ├── slack_tool.py
│   │           ├── notion_tool.py
│   │           └── growth_memory_tool.py
│   ├── anthropic/       # Claude API clients
│   │   └── summarization_client.py  # Session 요약 (6가지 단위)
│   ├── mongodb/         # MongoDB client, collections, adapters
│   │   └── collections/
│   │       ├── eventlog_adapter.py       # EventLog aggregation (analytics tools)
│   │       ├── growth_memory_adapter.py  # $vectorSearch 지원
│   │       └── subagent_trace_adapter.py # SubAgentTrace collection
│   ├── repositories/    # Repository implementations
│   │   └── mongodb/
│   │       ├── growth_memory.py    # vector_search 구현
│   │       └── subagent_trace.py   # SubAgentTrace repository
│   ├── aws/             # SQS producer/consumer
│   ├── openai/          # OpenAI embedding client (text-embedding-3-small)
│   ├── external/        # Slack, Notion API clients
│   └── uow/             # Unit of Work implementation
└── entrypoints/
    ├── api/             # FastAPI
    │   ├── app.py           # Lifespan, middleware, routes
    │   ├── routes/agent.py  # Agent session endpoints
    │   └── schemas/agent.py # Request/Response schemas
    └── worker/          # SQS Worker
        ├── app.py           # Worker entry point
        ├── dependencies.py  # Worker dependencies
        └── tasks/
            ├── agent_tasks.py   # @task process_agent_response
            └── memory_tasks.py  # @task archive_session_to_memory

Dockerfile               # Python 3.12-slim, API/Worker 컨테이너
docker-compose.yml       # API + Worker 서비스 (cloud MongoDB/SQS 사용)

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
│  2. Execute SupervisorAgentClient.stream_query()                │
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
                 memory_repo, embedding_client, trace_repo): ...
    async def enqueue_message(session_id, content, sqs_producer) -> MessageEnqueueResultVO
    async def execute_agent_response(session_id, user_message_id, sqs_producer=None) -> None
    # Tool dependencies (including RAG, trace) are passed to SupervisorAgentClient
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
    trace_repo = WorkerDependencies.get_trace_repo()

    service = AgentOrchestrationService(
        db_client=db_client,
        eventlog_adapter=eventlog_adapter,
        slack_client=slack_client,
        notion_client=notion_client,
        config=config,
        memory_repo=memory_repo,
        embedding_client=embedding_client,
        trace_repo=trace_repo,
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

### Option 1: Docker (Recommended)
```bash
cp .env.example .env  # Configure API keys
docker-compose up --build
# API: http://localhost:8000, Worker starts automatically
# Test: python scripts/agent_chat.py
```

### Option 2: Local Development
```bash
./void run api      # FastAPI with --reload
./void run worker   # SQS Consumer
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
1. `adapters/agent/subagents/tools/xxx_tool.py` - `create_xxx_tools(dependencies)` 팩토리 함수
2. `adapters/agent/subagents/tools/__init__.py` - 팩토리 함수 export 추가
3. Sub-agent에 Tool 추가 시: 해당 sub-agent의 `create_tools()` 메서드에 추가
4. `entrypoints/worker/dependencies.py` - 필요시 의존성 추가

### New Sub-Agent
1. `adapters/agent/subagents/xxx.py` - BaseSubAgent 상속, `create_tools()` 구현
2. `adapters/agent/subagents/__init__.py` - export 추가
3. `adapters/agent/supervisor/tools/subagent_tools.py` - `call_xxx` Tool 추가
4. `adapters/agent/supervisor/client.py` - sub-agent 인스턴스 생성

---

## Agent System Architecture

### Supervisor + Sub-Agents Pattern

Growth Agent는 Supervisor가 전문화된 Sub-Agent들을 Tool로 호출하는 협업 구조:

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Supervisor Agent                             │
│  - Model: claude-opus-4-5                                           │
│  - Tools: call_slack, call_product, call_data, call_memory          │
│  - 직접 외부 API 호출 없음, 서브에이전트 결과만 수신                 │
│  - 메인 세션 히스토리 관리                                           │
└─────────────────────────────┬───────────────────────────────────────┘
                              │ (Tool Call)
      ┌───────────────┬───────┴───────┬───────────────┐
      ▼               ▼               ▼               ▼
┌───────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Slack    │ │  Product    │ │    Data     │ │   Memory    │
│  Agent    │ │  Domain     │ │  Analysis   │ │   Agent     │
│           │ │  Agent      │ │  Agent      │ │             │
│ opus-4-5  │ │  opus-4-5   │ │  opus-4-5   │ │  opus-4-5   │
├───────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤
│ Tools:    │ │ Tools:      │ │ Tools:      │ │ Tools:      │
│ - list_ch │ │ - list_pages│ │ - eventlog  │ │ - search_   │
│ - get_msg │ │ - get_page  │ │   _specs    │ │   memory    │
│           │ │ - eventlog  │ │ - eventlog  │ │ - get_sess  │
│           │ │   _specs    │ │   _agg      │ │   _messages │
└───────────┘ └─────────────┘ └─────────────┘ └─────────────┘
      │               │               │               │
      ▼               ▼               ▼               ▼
 [Slack API]    [Notion API]   [EventLog DB]   [GrowthMemory]
```

### Sub-Agent 역할 분담

| Agent | 역할 | Tools | 핵심 책임 |
|-------|------|-------|-----------|
| **SlackAgent** | 팀 커뮤니케이션 | `list_slack_channels`, `get_slack_messages` | 채널 자율 선택, 요약/원문 판단 |
| **ProductDomainAgent** | 프로덕트 지식 | `list_notion_pages`, `get_notion_page`, `get_eventlog_specs` | 배경지식 제공, 적절한 요약 |
| **DataAnalysisAgent** | 데이터 분석 | `get_eventlog_specs`, `run_eventlog_aggregation` | 다중 쿼리 실행, 쿼리+결과 반환 |
| **MemoryAgent** | 과거 인사이트 | `search_growth_memory`, `get_session_messages` | RAG 검색, 과거 경험 조언 |

**Note**: `get_eventlog_specs`는 ProductDomainAgent(컨텍스트용)와 DataAnalysisAgent(쿼리 작성용)에 의도적으로 중복 배치.

### Slack Tool Enhanced Features

`get_slack_messages` Tool은 다음 요소를 지원:

| 요소 | 처리 방식 |
|------|-----------|
| **text** | 메시지 본문 (500자 제한) |
| **blocks** | rich_text, section, header, context 블록에서 텍스트 추출 |
| **attachments** | 링크 프리뷰를 마크다운 링크로 변환 |
| **files** | 파일명 + 링크 형태로 간략화 |
| **thread replies** | `reply_count > 0`인 메시지에서 스레드 답글 자동 조회 (들여쓰기 표시) |

```python
# adapters/agent/subagents/tools/slack_tool.py 헬퍼 함수
_extract_block_text(blocks)    # 블록에서 텍스트 추출
_format_attachments(attachments)  # 첨부파일 → 마크다운 링크
_format_files(files)           # 파일 → 마크다운 링크
_format_message(msg, indent)   # 메시지 포맷팅 (스레드 들여쓰기 지원)
```

```python
# adapters/external/slack_client.py
async def get_thread_replies(channel_id, thread_ts, limit) -> Dict:
    """conversations.replies API로 스레드 답글 조회 (부모 메시지 제외)"""
```

### Tool Factory Pattern (Dependency Injection)

Sub-Agent Tools는 팩토리 함수 패턴으로 의존성 주입:

```python
# adapters/agent/subagents/tools/eventlog_tool.py
def create_eventlog_tools(eventlog_adapter) -> List:
    @tool("run_eventlog_aggregation", ...)
    async def run_eventlog_aggregation(args): ...

    return [run_eventlog_aggregation]
```

### Built-in Tools

Supervisor 및 모든 Sub-Agent에서 사용 가능한 기본 도구:

| Tool | 용도 |
|------|------|
| **WebSearch** | 외부 정보 검색 (벤치마크, 트렌드, 경쟁사) |
| **WebFetch** | URL 콘텐츠 분석 (공유 링크, 문서) |
| **TodoWrite** | 분석 진행 상황 추적 |
| **SequentialThinking** | 복잡한 문제의 단계별 구조화된 사고 |

```python
# adapters/agent/subagents/base.py
SUBAGENT_BUILTIN_TOOLS = [
    "WebSearch",
    "WebFetch",
    "TodoWrite",
    "mcp__sequential-thinking__sequentialthinking",
]
```

### External MCP Integration

npx를 통해 외부 MCP 서버를 Supervisor와 모든 Sub-Agent에 통합:

```python
# supervisor/options.py, subagents/base.py
mcp_servers={
    "internal-tools": internal_mcp_server,  # SDK MCP (인-프로세스)
    "sequential-thinking": {                 # External MCP (npx)
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    }
}
```

**Requirements**: Node.js (npx 실행용)

### BaseSubAgent Pattern

모든 Sub-Agent는 공통 인터페이스 상속:

```python
class BaseSubAgent(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def system_prompt(self) -> str: ...

    @abstractmethod
    def create_tools(self) -> List[Callable]: ...

    async def execute(self, task: str) -> SubAgentExecutionResult:
        """단일 실행 후 결과와 내부 이벤트 반환. Stateless."""
        ...
```

### SupervisorAgentClient Flow

```
┌──────────────────────────────────────────────────────┐
│              AgentOrchestrationService               │
│  execute_agent_response(session_id, user_message_id) │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│               SupervisorAgentClient                  │
│  (Supervisor + Sub-Agents 협업 wrapper)              │
├──────────────────────────────────────────────────────┤
│  __init__(eventlog_adapter, slack_client, ...)       │
│  → Sub-agents 생성 (Slack, Product, Data, Memory)    │
│  → create_subagent_tools() 로 Supervisor Tools 생성  │
├──────────────────────────────────────────────────────┤
│  stream_query() → yields AgentStreamEvent            │
│  - TEXT: Supervisor 텍스트 응답                      │
│  - TOOL_USE: Sub-agent 호출 (call_slack 등)          │
│  - COMPLETE: 최종 완료 + claude_session_id           │
└──────────────────────┬───────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────┐
│           Supervisor MCP Server (Tools)              │
├──────────────────────────────────────────────────────┤
│  call_slack:   SlackAgent.execute(task) 호출         │
│  call_product: ProductDomainAgent.execute(task) 호출 │
│  call_data:    DataAnalysisAgent.execute(task) 호출  │
│  call_memory:  MemoryAgent.execute(task) 호출        │
└──────────────────────────────────────────────────────┘
```

### Message Flow Example

```
[User] → "리텐션이 떨어지는 원인을 분석해줘"
           │
           ▼
[Supervisor] → 분석 계획 수립
           │
           ├─ call_data("D+7 리텐션 추이 분석")
           │     └─ DataAnalysisAgent 실행
           │          └─ get_eventlog_specs(...)
           │          └─ run_eventlog_aggregation(...) x N
           │          └─ 쿼리 + 결과 반환
           │
           ├─ call_memory("리텐션 관련 과거 분석 사례")
           │     └─ MemoryAgent 실행
           │          └─ search_growth_memory(...)
           │          └─ get_session_messages(...)
           │          └─ 쿼리 + 인사이트 반환
           │
           ├─ call_slack("리텐션 관련 팀 논의 검색")
           │     └─ SlackAgent 실행 (자율 채널 선택)
           │          └─ list_slack_channels()
           │          └─ get_slack_messages(...)
           │          └─ 요약 반환
           │
           └─ call_product("리텐션 관련 프로덕트 컨텍스트")
                 └─ ProductDomainAgent 실행
                      └─ list_notion_pages()
                      └─ get_notion_page(...)
                      └─ 요약 반환
           │
           ▼
[Supervisor] → 쿼리 검증 → 결과 종합 → 최종 응답
           │
           ▼
[DB 저장] ← 메인 세션에만 저장
           - User message
           - Supervisor의 Tool calls (call_data 등)
           - Sub-agent 전체 결과
           - Supervisor의 최종 응답
```

### SDK Session Resume Pattern

SDK가 conversation history를 자동 관리하므로, 매번 히스토리를 수동으로 전달할 필요 없음.

```
[First Message]
session.claude_session_id = None
SupervisorAgentClient(resume_session_id=None) → new SDK session
Save claude_session_id to database

[Subsequent Messages]
SupervisorAgentClient(resume_session_id="sdk-xxx")
→ SDK automatically resumes Supervisor context
→ Only new user message is passed to Supervisor
→ Sub-agents are stateless (no session resume)

[SDK Session Expired]
SDKSessionExpiredError → archive system session
Return error: "Session expired, create new session"
```

**Note**: 메시지는 DB에 저장되지만 이는 히스토리 조회용. Supervisor는 SDK session resume, Sub-agent는 항상 새 세션.

### Streaming Event Storage Pattern

Supervisor 응답 이벤트를 개별 메시지로 DB에 실시간 저장:

```python
async for event in supervisor.stream_query(user_message.content):
    if event.type == AgentMessageType.TEXT:
        # Supervisor 텍스트 응답 저장
        message = MessageEntity.create(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=event.content,
            metadata={"event_type": "text", "sequence": n}
        )
        await message_repo.create(message)

    elif event.type == AgentMessageType.TOOL_USE:
        # Sub-agent 호출 저장 (task 정보 포함)
        message = MessageEntity.create(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=f"Delegated to: {event.tool_call.name}",
            metadata={
                "event_type": "subagent_call",
                "sequence": n,
                "subagent": event.tool_call.name,
                "task": event.tool_call.input.get("task"),
                "tool_call": {"id": ..., "name": ..., "input": ...}
            }
        )
        await message_repo.create(message)

    elif event.type == AgentMessageType.COMPLETE:
        # claude_session_id 업데이트 (변경 시)
        if event.claude_session_id != resume_session_id:
            await session_repo.update_claude_session_id(...)
```

**장점**: 긴 응답도 실시간 진행 상황 조회 가능, 중단 시 부분 결과 보존, Sub-agent 호출 추적

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
# adapters/agent/subagents/tools/growth_memory_tool.py
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

---

## Sub-Agent Trace System

Sub-agent 내부 이벤트(TEXT, TOOL_USE 등)를 별도 Collection에 영구 저장하여 디버깅/분석 용도로 추적.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    messages (기존)                          │
│  metadata.subagent_call 이벤트에서 tool_call.id로 연결      │
└─────────────────────────────────────────────────────────────┘
                              │ 1:N
                              ▼
┌─────────────────────────────────────────────────────────────┐
│              SubAgentTrace (신규 Collection)                │
│  session_id, parent_message_id, agent_name, task           │
│  events: [{type, content, tool_name, tool_input, ...}]     │
│  result, started_at, completed_at, duration_ms             │
└─────────────────────────────────────────────────────────────┘
```

### SubAgentTraceEntity 구조

```python
@dataclass(eq=False, frozen=True)
class SubAgentTraceEntity(BaseEntity):
    session_id: str              # 부모 세션 ID
    parent_message_id: str       # Supervisor TOOL_USE 메시지 ID
    agent_name: str              # "slack", "product", "data", "memory"
    task: str                    # 위임받은 task
    created_at: datetime
    id: Optional[str] = None

    events: Optional[List[Dict[str, Any]]] = None  # 이벤트 목록
    result: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    model: Optional[str] = None
    error: Optional[str] = None
```

**events 배열 요소 구조**:
```python
{
    "sequence": int,
    "type": "text" | "tool_use",
    "timestamp": str,  # ISO format
    "content": str,              # type=text
    "tool_name": str,            # type=tool_use
    "tool_input": Dict           # type=tool_use
}
```

### SubAgentExecutionResult VO

Sub-agent 실행 결과를 trace 데이터와 함께 반환:

```python
@dataclass(frozen=True)
class SubAgentExecutionResult:
    final_response: str
    events: List[Dict[str, Any]]
    started_at: datetime
    completed_at: datetime
    duration_ms: int
    error: Optional[str] = None
```

### Trace Flow

```
Supervisor TOOL_USE (call_slack)
       ↓ parent_message_id 캡처 (tool_call.id)
SubAgent.execute(task)
       ↓ events 수집 (TEXT, TOOL_USE)
SubAgentExecutionResult 반환
       ↓
_save_trace() → SubAgentTraceEntity 생성 → MongoDB 저장
```

### MongoDB Index

```javascript
db.SubAgentTrace.createIndex({ "session_id": 1, "created_at": 1 })
db.SubAgentTrace.createIndex({ "parent_message_id": 1 })
```
