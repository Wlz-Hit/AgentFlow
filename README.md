# AgentFlow

A local-first orchestration runtime for coding agents, providing durable
scheduling, prompt queues, interruption recovery, and eventually multi-agent
execution.

**Status: early-stage.** This repository currently contains the architecture
foundation (TASK-001): a Python runtime skeleton with a health endpoint, a
React + Electron desktop shell, and documented Ports & Adapters boundaries.
Codex will be the first agent provider, but **provider-specific integration is
not implemented yet.**

## Architecture overview

```
Desktop UI (React + TypeScript)
        │  REST / WebSocket
        ▼
Python Runtime (FastAPI edge → AgentFlow core)
        │  AgentAdapter port
        ▼
Adapters (Codex first; Claude Code / Gemini CLI later)
```

- **Python Runtime** owns jobs, workflow, queues, scheduler, recovery, quota,
  adapters, persistence, and events.
- **React** owns presentation.
- **Electron** owns window lifecycle, tray, notifications, runtime process
  lifecycle, and packaging.
- **Core is provider-independent.** Codex lives only under
  `runtime/agentflow/adapters/codex/`.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full design.

## Repository structure

```
apps/desktop/     Electron + React + Vite UI
runtime/          Python 3.12 FastAPI runtime (uv)
schemas/          Shared schema placeholders
docs/             Architecture documentation
```

## Backend setup

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12.

```bash
cd runtime
uv sync
uv run pytest
uv run uvicorn agentflow.api.main:app --reload --host 127.0.0.1 --port 8000
```

Health check:

```text
GET http://127.0.0.1:8000/health
→ { "status": "ok", "service": "agentflow-runtime" }
```

## Frontend setup

Requires [Node.js](https://nodejs.org/) 22+ and [pnpm](https://pnpm.io/).

```bash
pnpm install
pnpm typecheck
pnpm build
pnpm dev:desktop
```

The desktop UI queries the runtime `/health` endpoint when the runtime is
listening on `127.0.0.1:8000`.

## Development commands

| Command | Where | Purpose |
| --- | --- | --- |
| `uv sync` | `runtime/` | Install Python dependencies |
| `uv run pytest` | `runtime/` | Backend tests |
| `uv run ruff check .` | `runtime/` | Lint |
| `pnpm install` | repo root | Install JS dependencies |
| `pnpm typecheck` | repo root | TypeScript check |
| `pnpm build` | repo root | Production Vite + Electron compile |
| `pnpm dev:desktop` | repo root | Vite renderer dev server |

## Current project status

Implemented:

- Monorepo layout and Cursor/agent guidance
- Runtime `/health` endpoint and test
- Desktop skeleton (AgentFlow splash + runtime health)
- Persistence and Codex adapter **packages** (placeholders only)

Not yet implemented:

- Codex / Claude / Gemini adapters
- Scheduler, Prompt Queue, workflow DAG, recovery
- Domain SQLite schema, WebSocket events
- Cloud sync, accounts, licensing, telemetry
