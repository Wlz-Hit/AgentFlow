# AgentFlow — guidance for coding agents

This repository is **AgentFlow**, a local-first orchestration runtime for coding
agents. Read this file before making changes.

## Before you change architecture

1. Read `docs/ARCHITECTURE.md`.
2. Read `.cursor/rules/agentflow-architecture.mdc`.
3. Do **not** silently change architectural decisions. If a task conflicts with
   these documents, **report the concern** and stop rather than working around it.

## Ownership

| Layer | Owns |
| --- | --- |
| Python Runtime (`runtime/`) | Jobs, workflow, queues, scheduler, recovery, quota, adapters, persistence, events |
| React (`apps/desktop/src/`) | Presentation only |
| Electron (`apps/desktop/electron/`) | Window/tray/notifications, runtime process lifecycle, packaging |

React must not contain scheduling or recovery logic. Electron must not contain
AgentFlow business logic.

## Provider independence (non-negotiable)

- Core (`runtime/agentflow/core/`) is provider-independent.
- Codex belongs **only** under `runtime/agentflow/adapters/codex/`.
- Do not import Codex, Claude, Gemini, Electron, React, or FastAPI from core.
- Do not put provider-specific fields on generic Job, Workflow, Queue,
  Scheduler, or Event types.
- The Scheduler must talk to **capabilities** (the AgentAdapter port), not
  hard-coded provider names.

Codex is the first planned adapter. It is not implemented in TASK-001 and must
not be smuggled into core “for convenience.”

## Local-first

- Default to local SQLite persistence and local processes.
- **No cloud dependency** without explicit architectural approval.
- Never store secrets in Git. Use `.env` (ignored) and `.env.example` (safe
  placeholders only).

## Engineering standards

- Prefer small, testable modules.
- Avoid unnecessary dependencies.
- Add tests for business logic.
- Run tests and type checking **before** declaring a task complete:
  - backend: `uv run pytest` from `runtime/`
  - frontend: `pnpm typecheck` and `pnpm build` from the repo root (or the
    desktop package)
- Keep application startup (FastAPI/Electron) separate from domain logic.

## Git safety

- Do not perform destructive Git operations (`git reset --hard`, force push,
  history rewrite) unless the user explicitly requests them.
- Do not work on `main` unless absolutely necessary; prefer feature branches.
- Do not merge to `main` unless asked.

## Out of scope until a dedicated task

Codex SDK integration, Codex login, quota monitoring, Prompt Queue behavior,
Scheduler behavior, workflow DAG, Claude/Gemini support, cloud sync, user
accounts, payments, licensing, telemetry, auto-updater, complex UI, and full
domain database schema.
