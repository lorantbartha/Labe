---
name: labe-repo
description: Working guide for agents operating in this repository. Covers architecture, local commands, DynamoDB/LocalStack setup, current project status, and repo-specific engineering rules.
---

# Labe Agent Guide

This repository is a full-stack goal-planning app:

- Backend: FastAPI, Pydantic v2, `aiodynamo`, `pydantic-ai`, OpenAI Responses API models
- Frontend: React 18, TypeScript, Vite, TanStack Query, Tailwind CSS
- Local infra: LocalStack for DynamoDB, DynamoDB Admin on `:8001`

Use this guide as the repo-specific source of truth alongside [README.md](/app/README.md), [CLAUDE.md](/app/CLAUDE.md), and [docs/worklog.md](/app/docs/worklog.md).

## Current State

The repo is beyond scaffolding. The implemented core flow is:

1. User creates a goal from a free-text description.
2. AI generates a concise title plus initial clarifying questions.
3. User submits answers across one or more rounds.
4. A sufficiency agent decides whether more questions are needed.
5. A planning agent generates milestone DAG + steps.
6. Users can view the plan, update milestone/step state, report blockers, and archive goals.

Known current gaps:

- Backend tests are still missing.
- Full end-to-end smoke testing against LocalStack is still needed.
- AI structured-output behavior has not been fully validated in practice.
- Step Detail page and Blocker Adaptation View are not built yet.
- Real auth is not wired; `x-user-id` currently falls back to `"default"`.

## Repository Layout

Top-level:

- [README.md](/app/README.md): developer quick start and stack summary
- [CLAUDE.md](/app/CLAUDE.md): detailed repo conventions and architecture notes
- [docs/worklog.md](/app/docs/worklog.md): session-by-session status and remaining work
- [`.env.template`](/app/.env.template): local env template
- [`.localstack/ready.d/setup.sh`](/app/.localstack/ready.d/setup.sh): LocalStack init hook

Backend:

- [main.py](/app/src/main.py): FastAPI app, lifespan, error handlers
- [app_config.py](/app/src/app_config.py): env-derived configuration
- [dependencies.py](/app/src/dependencies.py): DI chain
- [auth.py](/app/src/core/auth.py): user ID dependency
- [goals/models.py](/app/src/goals/models.py): Pydantic domain/API models
- [goals/repository.py](/app/src/goals/repository.py): DynamoDB access
- [goals/service.py](/app/src/goals/service.py): business logic
- [goals/router.py](/app/src/goals/router.py): HTTP endpoints
- [goals/ai.py](/app/src/goals/ai.py): `pydantic-ai` agents

Frontend:

- [App.tsx](/app/frontend/src/App.tsx): routes
- [api/goals.ts](/app/frontend/src/api/goals.ts): typed fetch wrappers
- [pages](/app/frontend/src/pages): dashboard, creation, clarifying Q&A, plan view
- [dagLayout.ts](/app/frontend/src/utils/dagLayout.ts): frontend DAG layout

## Backend Architecture

The backend follows a strict layered pattern:

Router -> Service -> Repository -> DynamoDB

Rules:

- Route handlers stay thin and call async service methods.
- Services and repositories are frozen dataclasses where applicable.
- Dependencies are injected via FastAPI `Depends()` through [dependencies.py](/app/src/dependencies.py).
- Table names come from config, never hard-coded in application logic.
- Fail fast. Do not wrap normal control flow in broad try/except blocks.

The DI chain for goals is:

- request app state -> DynamoDB client
- DynamoDB client -> `GoalsRepository`
- repository + `GoalsAI` -> `GoalsService`

## Data Model and Persistence

DynamoDB design:

- One goals table
- Partition key: `user_id`
- Sort key: `id`
- Table name: `GOALS_TABLE`, currently expected to be `Labe-Local-Goals`

Repository behavior:

- List goals via `Query` on `user_id`
- Individual goal access via `(user_id, id)`
- Questions, milestones, and steps are stored as JSON strings on the same goal item

Current auth behavior:

- [auth.py](/app/src/core/auth.py) returns `x-user-id` if provided
- Otherwise defaults to `"default"`

## AI Integration

AI logic lives in [goals/ai.py](/app/src/goals/ai.py).

Current model split:

- `gpt-5.4-nano` for clarifying questions and sufficiency checks
- `gpt-5.4-mini` with `openai_reasoning_effort="medium"` for plan generation

There are three agent responsibilities:

- Clarifying agent: extracts title and initial questions
- Sufficiency agent: decides if more clarification is needed
- Plan agent: emits milestone DAG plus ordered steps

Important implementation detail:

- The frontend computes milestone x/y layout from DAG topology.
- The backend should return dependencies and semantic plan structure, not presentation coordinates.

## Frontend Notes

The current frontend is desktop-oriented by design. Do not add mobile breakpoints unless explicitly requested.

Important screens already exist:

- Dashboard
- Goal creation
- Multi-round clarifying Q&A
- Plan view

Frontend data contracts should stay aligned with backend Pydantic models in:

- [models.py](/app/src/goals/models.py)
- [types/index.ts](/app/frontend/src/types/index.ts)

## Local Development

Backend:

```bash
cd /app/src
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --access-log
```

Frontend:

```bash
cd /app/frontend
npm run dev
```

Tests:

```bash
cd /app/src
ENVIRONMENT=testing python -m pytest
```

Lint/format:

```bash
/app/.devcontainer/scripts/pylint.sh
/app/.devcontainer/scripts/format.sh
```

## LocalStack and DynamoDB

Compose file:

- [docker-compose.yml](/app/src/docker-compose.yml)

Init hook:

- [setup.sh](/app/.localstack/ready.d/setup.sh)

Important repo-specific note:

- The LocalStack init script must be executable. This repo previously failed to create tables because [setup.sh](/app/.localstack/ready.d/setup.sh) lacked execute permissions and LocalStack logged `Permission denied`.

Useful verification commands:

```bash
aws dynamodb list-tables
aws dynamodb describe-table --table-name Labe-Local-Goals
aws dynamodb get-item --table-name Labe-Local-Goals --key '{"user_id":{"S":"default"},"id":{"S":"<goal-id>"}}'
curl http://localhost:4566/_localstack/health
```

Important environment-specific note:

- In this repo/devcontainer, plain `aws dynamodb ...` commands have worked reliably against LocalStack.
- Adding `--endpoint-url` has been unreliable here and has caused hangs or incorrect behavior during debugging.
- Prefer the plain `aws dynamodb ...` form first unless you have a confirmed reason to override the endpoint.

If tables are missing:

1. Confirm LocalStack is reachable.
2. Check LocalStack logs for `ready.d/setup.sh`.
3. Confirm the script is executable.
4. Restart or recreate LocalStack so READY hooks rerun.

## Repo-Specific Pitfalls

- [launch.json](/app/.vscode/launch.json) starts FastAPI from `/app/src`.
- [app_config.py](/app/src/app_config.py) should load the repo-root `.env`, not depend on the current working directory.
- `client.table(...)` from `aiodynamo` is synchronous; do not `await` it.
- Keep all imports at file top level.
- Do not introduce fake optional dependencies in FastAPI DI signatures.
- Do not hard-code resource names outside config.
- Do not add `ENVIRONMENT=testing` conditionals to production code for tests.

## Highest-Value Next Work

If continuing this repo without further prioritization, default to:

1. Verify LocalStack table creation and run a backend smoke test.
2. Add backend tests for `GoalsService`.
3. Add repository tests or integration tests against LocalStack.
4. Validate the multi-round AI flow with real model calls.
5. Implement the next missing product surface:
   Step Detail page or Blocker Adaptation View.

## Editing Guidance

When changing backend behavior:

- Update API contracts in backend and frontend together.
- Keep router/service/repository boundaries clean.
- Prefer domain-level fixes over UI-only workarounds.

When changing frontend behavior:

- Preserve the established neobrutalist visual system unless the user requests a redesign.
- Keep DAG layout logic in the frontend.

When adding tests:

- Prefer `app.dependency_overrides` and fakes over production conditionals.
- Start with service tests before deeper infra tests.

## When To Ask For More Info

Proceed without blocking unless one of these is needed:

- A live OpenAI API key is required for AI validation
- The user must choose between competing product priorities
- A change would alter intended product behavior, not just implementation quality
