# AgentFlow Architecture

AgentFlow is a **local-first desktop application** for orchestrating coding agents.
It is designed to monitor agent execution and quota status, recover interrupted
sessions, schedule work, maintain durable Prompt Queues, and support resumable
Jobs and Run Attempts.

This document is the source of truth for architectural boundaries. Read it before
changing structure, ownership, or dependency direction.

The project is **early-stage**. TASK-001 establishes the skeleton only. Codex is
the first planned provider implementation and **must not leak into core**.

---

## 1. Product purpose

AgentFlow helps an operator run coding agents as durable, recoverable work rather
than as one-off terminal sessions. Long-term capabilities include:

- monitoring execution and quota status
- automatically recovering interrupted agent sessions
- scheduling agent execution
- durable Prompt Queues
- resumable Jobs and Run Attempts
- multiple coding-agent providers (Codex first, then Claude Code, Gemini CLI, and others)

## 2. Local-first philosophy

- The default deployment is a machine the user controls.
- Persistence is local SQLite, not a hosted application database.
- The Python Runtime, Electron shell, and React UI all run locally.
- Cloud services, accounts, telemetry, licensing, and remote sync are **out of
  scope** unless an explicit architectural decision approves them.
- Secrets never belong in Git. Use `.env` locally (see `.env.example`).

## 3. High-level architecture

```
┌─────────────────────────────┐
│       Desktop UI            │
│   React + TypeScript        │
└─────────────┬───────────────┘
              │
        REST / WebSocket
              │
┌─────────────▼───────────────┐
│       Python Runtime        │
│                             │
│ Scheduler                   │
│ Workflow Engine             │
│ Prompt Queue                │
│ Recovery Engine             │
│ Event System                │
└─────────────┬───────────────┘
              │
       AgentAdapter Port
              │
        ┌─────▼─────┐
        │   Codex   │
        │  Adapter  │
        └───────────┘
```

Codex is **only the first adapter implementation**. The core talks to an
`AgentAdapter` port. Additional adapters (Claude Code, Gemini CLI, …) plug in
beside Codex without changing Job, Queue, Scheduler, or Event abstractions.

Conceptual dependency direction (Ports & Adapters / hexagonal):

```
Desktop UI
    ↓
Application/API boundary
    ↓
AgentFlow Core
    ↓
Ports / Interfaces
    ↓
Adapters
```

## 4. Python Runtime responsibilities

The Python Runtime owns **all business logic**:

- Jobs
- Workflow Engine
- Prompt Queue
- Scheduler
- State Machine
- Recovery Engine
- Quota Manager
- Agent Adapters
- Persistence
- Event history

It exposes HTTP REST for commands and queries, and will expose WebSocket for
live events. FastAPI is the HTTP adapter at the edge; **core must not import
FastAPI**.

Package layout:

```
runtime/agentflow/
  api/            FastAPI application (edge adapter)
  core/           provider-independent domain
    domain/
    scheduler/
    workflow/
    queue/
    recovery/
    events/
    ports/        interfaces used by core
  adapters/       provider implementations (Codex lives only here)
    codex/
  persistence/    SQLite / SQLAlchemy / Alembic
```

## 5. Electron responsibilities

Electron owns **desktop lifecycle**, not AgentFlow domain logic:

- desktop window lifecycle
- tray
- native notifications
- Python Runtime process lifecycle
- desktop packaging

Electron may start, stop, and supervise the runtime process. It must not
implement scheduling, queues, recovery, or provider-specific agent control.

## 6. React responsibilities

React owns **presentation**:

- dashboard
- task views
- queue views
- timeline views
- settings views

React talks to the runtime through a thin API layer (`apps/desktop/src/api`).
It must not contain core scheduling, recovery, or provider orchestration logic.

## 7. Ports & Adapters design

- **Core** defines ports (interfaces / protocols) for agents, persistence, and
  clocks/events as needed.
- **Adapters** implement those ports (Codex CLI/SDK, SQLite, FastAPI, later
  other providers).
- **API** translates HTTP/WebSocket into application use-cases that call core.
- Inward dependencies only: adapters and frameworks depend on core, never the
  reverse.

`runtime/agentflow/core/` **must remain provider-independent**.

Forbidden in core:

- imports of Codex, Claude, Gemini, Electron, React, or FastAPI
- Codex-specific (or any provider-specific) fields on generic Job, Workflow,
  Queue, Scheduler, or Event types

## 8. AgentAdapter concept

Long-term, adapters implement a shared capability surface similar to:

- start session
- resume session
- run input
- interrupt
- observe events
- query usage/quota
- health check

The Scheduler interacts with **capabilities**, not hard-coded provider names.

Intended shape (not fully implemented in TASK-001):

```
AgentAdapter
    ├── CodexAdapter
    ├── ClaudeCodeAdapter
    └── GeminiAdapter
```

Placeholder package: `runtime/agentflow/adapters/codex/`. Do not add Codex SDK
integration, login, or quota monitoring until a dedicated task.

## 9. Scheduler concept

The Scheduler will:

- decide when a Job or queue item may run
- respect quota, pause, and recovery state
- invoke the selected adapter through the AgentAdapter port
- never branch on `"codex"` / `"claude"` / `"gemini"` as business logic

Implementation of scheduling behavior is deferred.

## 10. Prompt Queue concept

A Prompt Queue is a **durable, ordered collection of work items** owned by the
runtime (not the UI). Items survive restarts via SQLite. The UI displays and
edits queues; the runtime executes them. Queue behavior is deferred.

## 11. Event-driven communication

The runtime will be event-driven. Example event names (catalog only; not
implemented yet):

```
JOB_CREATED
RUN_STARTED
QUOTA_WARNING
QUOTA_EXHAUSTED
RUN_PAUSED
QUOTA_RESTORED
SESSION_RESUMED
RUN_COMPLETED
JOB_COMPLETED
```

- **HTTP REST** — commands and queries
- **WebSocket** — live event delivery to the desktop UI

Do not implement the full event bus in TASK-001. Reserve
`runtime/agentflow/core/events/` for this work.

## 12. SQLite persistence

AgentFlow is local-first. The planned database is **SQLite**, accessed through
SQLAlchemy 2 and migrated with Alembic.

Future domain tables (do not create all of these yet):

- `jobs`
- `workflow_steps`
- `queue_items`
- `agent_sessions`
- `run_attempts`
- `events`
- `quota_snapshots`
- `settings`

TASK-001 only establishes the persistence package and documents this model.

## 13. Why Codex must not leak into core abstractions

Codex is an **adapter**, not the product model. If Job, Workflow, Queue,
Scheduler, or Event types carry Codex-only fields or assume Codex session
semantics:

- Claude Code and Gemini CLI cannot be added without rewriting core
- recovery and quota logic become provider-specific
- tests of core would require Codex

Keep provider details behind `AgentAdapter` and adapter-specific mapping
modules under `runtime/agentflow/adapters/<provider>/`.

## 14. Future multi-agent extensibility

New providers should:

1. Implement the AgentAdapter port.
2. Live under `runtime/agentflow/adapters/<name>/`.
3. Register via configuration, not core conditionals.
4. Map provider events onto the shared runtime event catalog.

The desktop UI should treat providers as selectable backends, not as separate
products.

---

## Current status (TASK-001)

Implemented:

- monorepo layout (pnpm workspace + Python runtime)
- FastAPI `/health` at the API edge
- React/Electron desktop skeleton
- persistence package placeholder
- adapter package placeholder for Codex
- this document, `AGENTS.md`, and Cursor architecture rules

Not implemented (intentionally):

- Codex SDK, login, quota monitoring
- Prompt Queue / Scheduler / workflow DAG behavior
- Claude / Gemini support
- domain database schema
- WebSocket event stream
- cloud sync, accounts, payments, licensing, telemetry, auto-update
