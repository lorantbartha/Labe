# Labe

Labe helps makers and founders turn ambitious goals into structured, trackable plans — and keeps them honest as reality changes.

You describe a goal. Labe asks a few targeted clarifying questions — your available time, starting point, hard constraints. Then it generates a phased, constraint-aware plan broken into concrete milestones with clear actions. As you move forward you can mark progress, flag blockers, and ask Labe to adapt. The plan is a living thing, not a static document.

---

## Stack

**Backend**
- Python 3.13, FastAPI, Pydantic v2
- `pydantic-ai` + OpenAI `gpt-5.4-nano` (Q&A) and `gpt-5.4-mini` with reasoning (plan generation) via Responses API
- DynamoDB via `aiodynamo` (async) for persistence
- AWS LocalStack for local DynamoDB emulation
- DynamoDB Admin UI at `localhost:8001`
- Ruff, Flake8, Pyright, isort for linting
- pip-tools for dependency management
- pytest with async support

**Frontend**
- React 18 + TypeScript + Vite 5
- TanStack Query v5 for server state
- React Router v6 for SPA routing
- Tailwind CSS v3 with a custom neobrutalist design system
- Material Symbols Outlined icon font
- Desktop-only layout (no mobile breakpoints)

---

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)
- [VS Code](https://code.visualstudio.com/) with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)

---

## Quick Start

### 1. Set up environment variables

```bash
cp .env.template .env
# Fill in your OPENAI_API_KEY
```

### 2. Start the dev container

Open the folder in VS Code, then when prompted click **"Reopen in Container"**.

VS Code will build the Docker image, start LocalStack, and drop you into a fully configured dev environment. This takes a few minutes on first run.

### 3. Start the backend

Press **F5** (or run `FastAPI Server` from the Run & Debug panel), or from a terminal:

```bash
cd src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --access-log
```

### 4. Start the frontend

Run `Vite Dev Server` from the Run & Debug panel, or from a terminal:

```bash
cd frontend
npm install   # first time only
npm run dev
```

### 5. Open the app

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Interactive API docs | http://localhost:8000/docs |
| DynamoDB Admin | http://localhost:8001 |

---

## Without Dev Container

```bash
# Start backend + LocalStack via Docker Compose
docker-compose -f src/docker-compose.yml up --build

# Start frontend separately
cd frontend
npm install
npm run dev
```

---

## Running Tests

```bash
# From inside the dev container, from /app/src:
ENVIRONMENT=testing python -m pytest

# Verbose
ENVIRONMENT=testing python -m pytest -v

# With coverage
ENVIRONMENT=testing python -m pytest --cov=.
```

---

## Code Quality

```bash
# Run all linters (Ruff + Flake8 + Pyright + isort)
.devcontainer/scripts/pylint.sh

# Auto-format
.devcontainer/scripts/format.sh
```

---

## Dependency Management

```bash
# 1. Add a package to src/requirements.in
# 2. Recompile the lockfile
pip-compile src/requirements.in

# 3. Sync your environment
pip-sync src/requirements.txt
```

---

## DynamoDB Table Design

All tables use a **composite key**: `user_id` (HASH) + `id` (RANGE). This allows efficient per-user queries without a table scan and is ready for real auth — swap `"default"` for a real user ID when auth is wired up.

Table names always come from environment variables (see `app_config.py`), never hard-coded.

---

## Adding a Feature Module

```
src/
└── my_feature/
    ├── __init__.py
    ├── models.py       # Pydantic models
    ├── repository.py   # DynamoDB access (frozen dataclass)
    ├── service.py      # Business logic (frozen dataclass)
    ├── router.py       # FastAPI endpoints
    └── tests/
        └── test_service.py
```

1. Create the module directory and files above.
2. Add factory functions in `src/dependencies.py`.
3. Register the router in `src/main.py`.
4. Add a table creation command to `.localstack/ready.d/setup.sh`.
5. Add the table name env var to `src/docker-compose.yml` and `.env.template`.

---

## Project Layout

```
.
├── README.md
├── CLAUDE.md                          # AI coding assistant instructions
├── pyproject.toml                     # Ruff, isort, pyright, pytest config
├── .env.template                      # Environment variable template
├── .gitignore
├── .devcontainer/
│   ├── devcontainer.json
│   └── scripts/
│       ├── post_create.sh
│       ├── pylint.sh
│       └── format.sh
├── .localstack/
│   └── ready.d/setup.sh              # LocalStack init (creates DynamoDB tables)
├── .vscode/
│   ├── launch.json                   # FastAPI Server, Vite Dev Server, Run all tests
│   └── tasks.json
├── docs/
│   ├── design-brief.md
│   ├── user-stories.md
│   └── worklog.md                    # Decisions, done/todo log
├── frontend/
│   ├── package.json
│   ├── vite.config.ts                # Proxies /goals and /health to :8000
│   ├── tailwind.config.ts
│   └── src/
│       ├── App.tsx                   # Route definitions
│       ├── api/goals.ts              # Typed fetch wrappers
│       ├── types/index.ts            # TypeScript interfaces
│       ├── utils/dagLayout.ts        # DAG layout algorithm (longest-path layering)
│       ├── pages/                    # DashboardPage, GoalCreationPage,
│       │                             #   ClarifyingQAPage, PlanViewPage
│       └── components/
│           ├── layout/               # TopNavBar, SideNavBar
│           └── ui/                   # GoalCard, StatusBadge, ProgressBar
└── src/
    ├── Dockerfile
    ├── docker-compose.yml
    ├── requirements.in                # Direct dependencies (source of truth)
    ├── requirements.txt               # Compiled lockfile (generated)
    ├── app_config.py                  # Env-derived config singleton
    ├── main.py                        # App entry point + lifespan
    ├── dependencies.py               # DI factory functions
    ├── .flake8                        # Flake8 config (max-line-length = 120)
    └── goals/
        ├── models.py                 # Pydantic models
        ├── repository.py             # DynamoDB access (GoalsRepository)
        ├── ai.py                     # pydantic-ai agents (GoalsAI)
        ├── service.py                # Business logic (GoalsService)
        └── router.py                 # FastAPI endpoints
```
