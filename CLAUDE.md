# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

**Labe** is an AI-powered goal planning tool. Users describe a goal in free text; Labe asks clarifying questions via an LLM agent, then generates a structured plan of milestones and steps. Users track progress, flag blockers, and the plan adapts over time.

**Backend:** FastAPI + DynamoDB (aiodynamo) + pydantic-ai (OpenAI gpt-5.4-nano / gpt-5.4-mini via Responses API)
**Frontend:** React 18 + Vite + TypeScript + Tailwind CSS (neobrutalist design system)
**Local infra:** LocalStack for DynamoDB emulation, DynamoDB Admin UI at :8001

## Common Commands

### Running the Application

```bash
# Backend — from /app/src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --access-log

# Frontend — from /app/frontend
npm run dev

# VS Code: F5 → "FastAPI Server" or "Vite Dev Server"
# Full stack via Docker Compose (backend + LocalStack only, run frontend separately):
docker-compose -f src/docker-compose.yml up --build
```

### Testing

```bash
# Run all tests (from /app/src)
ENVIRONMENT=testing python -m pytest

# Run tests for a specific module
ENVIRONMENT=testing python -m pytest goals/tests/

# Run a single test
ENVIRONMENT=testing python -m pytest goals/tests/test_service.py::test_create_goal

# Verbose output
ENVIRONMENT=testing python -m pytest -v

# With coverage
ENVIRONMENT=testing python -m pytest --cov=.
```

### Code Quality

```bash
# Run all linters (from /app/src)
.devcontainer/scripts/pylint.sh

# Auto-format code
.devcontainer/scripts/format.sh

# Or use VS Code tasks: "lint check", "format", "ruff fix"
```

### Dependency Management

```bash
# Add package to requirements.in, then:
pip-compile src/requirements.in
pip-sync src/requirements.txt
```

## Architecture

### Layered Service Pattern

The codebase follows a strict layered architecture:

```
Router (FastAPI endpoints)
    ↓
Service (Business logic)
    ↓
Repository (Data access)
    ↓
Models (Pydantic)
    ↓
DynamoDB / external storage
```

### Key Directories

```
src/
├── main.py               # FastAPI app entry point + lifespan (aiohttp session, DynamoDB client)
├── app_config.py         # Env-derived config singleton (table names, API keys)
├── dependencies.py       # DI factory chain: Client → Repository → Service
└── goals/
    ├── models.py         # Pydantic models (Goal, Milestone, Step, ClarifyingQuestion, …)
    ├── repository.py     # GoalsRepository — DynamoDB access via aiodynamo
    ├── ai.py             # GoalsAI — pydantic-ai agents (ClarifyingAgent, PlanAgent)
    ├── service.py        # GoalsService — business logic (async, frozen dataclass)
    ├── router.py         # FastAPI endpoints
    └── tests/
        └── test_*.py

frontend/src/
├── App.tsx               # Route definitions
├── api/goals.ts          # Typed fetch wrappers for all endpoints
├── types/index.ts        # TypeScript interfaces mirroring backend Pydantic models
├── utils/dagLayout.ts    # DAG layout algorithm (longest-path layering → x/y positions)
├── pages/                # DashboardPage, GoalCreationPage, ClarifyingQAPage, PlanViewPage
└── components/
    ├── layout/           # TopNavBar, SideNavBar
    └── ui/               # GoalCard, StatusBadge, ProgressBar
```

### Dependency Injection

All services and repositories use FastAPI's `Depends()` via `dependencies.py`. The full chain for goals:

```python
# dependencies.py
def get_dynamo_client(request: Request) -> Client:
    return request.app.state.dynamo_client          # set in lifespan

def get_goals_repository(client: Client = Depends(get_dynamo_client)) -> GoalsRepository:
    return GoalsRepository(client=client, table_name=app_config.goals_table)

def get_goals_service(
    goals_repo: GoalsRepository = Depends(get_goals_repository),
) -> GoalsService:
    return GoalsService(goals_repo=goals_repo, goals_ai=_goals_ai)
```

Services and repositories are **frozen dataclasses** — dependencies are injected, never stored as mutable state:

```python
@dataclass(frozen=True)
class GoalsService:
    goals_repo: GoalsRepository
    goals_ai: GoalsAI
```

**Never make injected dependencies optional** (i.e., don't use `= None`). FastAPI always
provides them — optional typing creates false optionality and hides missing dependencies.

### Database Design

Use DynamoDB via `aiodynamo` (async). The standard pattern in this project:

- **Composite key:** `user_id` (HASH) + `id` (RANGE) — enables per-user `Query` without a scan
- Table names always come from `app_config.py`, which reads from env vars — never hard-coded
- Nested lists (questions, milestones, steps) are stored as **JSON strings** in dedicated attributes, not DynamoDB Lists/Maps (avoids null-type serialisation issues with Pydantic)

```python
# app_config.py — single source of truth
class AppConfig:
    goals_table: str = os.environ["GOALS_TABLE"]
    openai_api_key: str | None = os.environ.get("OPENAI_API_KEY")

app_config = AppConfig()
```

## Code Style Guidelines

### Import Organization

**Always place all imports at the top of the file.** Never use local imports inside
functions or methods.

```python
# Good
from app_config import app_config

class MyService:
    def method(self):
        config = app_config.something
```

```python
# Bad
class MyService:
    def method(self):
        from app_config import app_config  # local import — don't do this
```

**Circular imports:** If you hit a circular import, do not use `TYPE_CHECKING` or local
import workarounds. Ask how to break the dependency instead (move shared types, invert
dependencies, restructure modules).

### Formatting Rules (from pyproject.toml)

- **Line length:** 120 characters
- **Target version:** Python 3.13
- **Quote style:** Double quotes
- **Indentation:** 4 spaces (no tabs)
- **Import sorting:** Black profile with isort

### Type Hints

Use type hints for all function signatures:

```python
async def get_item(self, item_id: str) -> Item | None:
    ...
```

Use `T | None` not `Optional[T]`.

## Development Patterns

### AI Agents (pydantic-ai)

AI logic lives in `goals/ai.py` as a `GoalsAI` dataclass with three agents:

- **ClarifyingAgent** — takes a free-text goal description, returns an AI-generated title + initial clarifying questions (`_QuestionsResult` has `title: str` + `questions`). Uses `_fast_model`.
- **SufficiencyAgent** — evaluates all Q&A pairs and decides whether to ask follow-up questions or proceed to plan generation; no hard cap in code, agent decides. Uses `_fast_model`.
- **PlanAgent** — takes goal description + Q&A pairs, returns milestones (DAG via `depends_on_node_ids`, each with a `description`) + steps (with `order`). Uses `_reasoning_model` with `reasoning_effort="medium"`.

Two model tiers using `OpenAIResponsesModel` (Responses API — required for reasoning):

```python
from pydantic_ai.models.openai import OpenAIResponsesModel

_fast_model = OpenAIResponsesModel("gpt-5.4-nano")       # Q&A, sufficiency
_reasoning_model = OpenAIResponsesModel("gpt-5.4-mini")  # plan generation

_plan_agent: Agent[None, _PlanOutput] = Agent(
    model=_reasoning_model,
    output_type=_PlanOutput,
    model_settings={"openai_reasoning_effort": "medium"},
    system_prompt="...",
)
result = await _agent.run(prompt)
data = result.output   # typed as _PlanOutput
```

Use `OpenAIResponsesModel`, not the deprecated `OpenAIModel` (Chat Completions). The `reasoning_effort` setting only works with the Responses API model class.

### Authentication

`user_id` is stored in DynamoDB as the partition key. Currently hardcoded to `"default"` in `GoalsRepository`. When real auth is added, wire an `x-user-id` header dependency and pass it through the service to the repository:

```python
# future: core/auth.py
async def get_user_id(x_user_id: str = Header(None)) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing x-user-id header")
    return x_user_id

ValidatedUserIdDep = Annotated[str, Depends(get_user_id)]
```

### Streaming Responses

For long-running operations use Server-Sent Events (SSE):

```python
from collections.abc import AsyncGenerator
from fastapi.responses import StreamingResponse

async def generate_stream() -> AsyncGenerator[str, None]:
    yield f"event: metadata\ndata: {json.dumps(metadata)}\n\n"
    async for chunk in data_source:
        yield f"event: chunk\ndata: {json.dumps({'content': chunk})}\n\n"
    yield f"event: done\ndata: {{}}\n\n"

@router.post("/stream")
async def stream_endpoint(request: RequestModel) -> StreamingResponse:
    return StreamingResponse(generate_stream(), media_type="text/event-stream")
```

### Adding a New Feature Module

1. Create `src/<feature>/` directory
2. Add `models.py` — Pydantic models
3. Add `repository.py` — `@dataclass(frozen=True)` with `client: Client` + `table_name: str`
4. Add `service.py` — `@dataclass(frozen=True)` with injected repo (and AI if needed)
5. Add `router.py` — FastAPI endpoints, all service calls `await`-ed
6. Add `tests/test_*.py`
7. Add DI factory functions to `dependencies.py`
8. Register the router in `main.py`
9. Add table creation to `.localstack/ready.d/setup.sh`
10. Add table name env var to `docker-compose.yml`, `.env.template`, and `app_config.py`

### Creating API Endpoints

```python
from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_item_service
from example.service import ItemService

router = APIRouter(prefix="/items", tags=["items"])

@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: str,
    service: ItemService = Depends(get_item_service),
) -> ItemResponse:
    item = await service.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return ItemResponse.from_item(item)
```

### Writing Tests

Use `app.dependency_overrides` to inject fake repositories — no `ENVIRONMENT` conditionals in production code:

```python
# conftest.py
@pytest.fixture
def fake_repo() -> FakeGoalsRepository:
    return FakeGoalsRepository()

@pytest.fixture
def client(fake_repo: FakeGoalsRepository) -> TestClient:
    app.dependency_overrides[get_goals_repository] = lambda: fake_repo
    yield TestClient(app)
    app.dependency_overrides.clear()
```

Use real domain objects instead of mocks where possible. Only use `AsyncMock` for
dependencies that have async methods when a real fake is impractical:

```python
mock_repo = MagicMock()
mock_repo.get_goal = AsyncMock(return_value=goal)
mock_repo.put_goal = AsyncMock(return_value=None)
```

## Error Handling

**Fail fast.** Do not wrap everything in try/catch. Let exceptions propagate to top-level
handlers in `main.py`. Add custom exception handlers there for domain errors:

```python
@app.exception_handler(ItemNotFoundError)
async def item_not_found_handler(request: Request, exc: ItemNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc)})
```

Create specific domain exceptions:

```python
class ItemNotFoundError(RuntimeError):
    def __init__(self, item_id: str) -> None:
        super().__init__(f"Item '{item_id}' not found")
        self.item_id = item_id
```

## Environment Setup

### Docker Compose Stack

```bash
docker-compose -f src/docker-compose.yml up --build
```

Services started by docker-compose:
- **App (backend):** http://localhost:8000
- **LocalStack (AWS):** http://localhost:4566
- **DynamoDB Admin:** http://localhost:8001

Frontend is run separately (`npm run dev` from `/app/frontend`):
- **Frontend:** http://localhost:5173

### Environment Variables

Copy `.env.template` to `.env` and fill in values. Key variables:
- `GOALS_TABLE` — DynamoDB table name (e.g. `Labe-Local-Goals`)
- `OPENAI_API_KEY` — required for AI features (clarifying questions + plan generation)
- `AWS_ENDPOINT_URL` — LocalStack endpoint (local only, set automatically in docker-compose)
- `AWS_DEFAULT_REGION` — defaults to `us-east-1`
- `LOG_LEVEL` — `debug` / `info` / `warning`

### LocalStack Setup

Add DynamoDB tables and S3 buckets to `.localstack/ready.d/setup.sh`. The script runs
automatically when LocalStack starts. Follow the commented examples in that file.

## Common Pitfalls

1. **Circular imports:** Ask how to refactor rather than using `TYPE_CHECKING` or local imports.
2. **Overly defensive code:** Follow "fail fast" — don't wrap logic in try/catch everywhere.
3. **Optional dependencies:** Never use `= None` for injected dependencies; it hides bugs.
4. **Hard-coded resource names:** All table names must come from `app_config.py` / env vars.
5. **Missing async/await:** All I/O (DynamoDB, OpenAI, HTTP calls) must be `async`/`await`.
6. **Type hints:** Use `T | None` not `Optional[T]`.
7. **`client.table()` is synchronous:** Don't `await` it — it returns a `Table` wrapper immediately.
8. **pydantic-ai result access:** Use `result.output`, not `result.data` (changed in v1+).
9. **Testing with ENVIRONMENT:** Don't add `ENVIRONMENT=testing` conditionals in production code. Use `app.dependency_overrides` instead.
10. **Flake8 does not read `pyproject.toml`:** Line length and other Flake8 settings must be in `/app/src/.flake8`, not in `pyproject.toml`. Ruff and isort are both configured for 120 chars; Flake8 must match via `.flake8`.

## Logging

Use a module-level logger:

```python
import logging

logger = logging.getLogger(__name__)

logger.info("Processing item %s", item_id)
logger.warning("Could not load config: %s", error)
logger.error("Failed to save item", exc_info=True)
```
