# AgentFlow Architecture

AgentFlow is a **local-first desktop application** for orchestrating coding agents.
It is designed to monitor agent execution and quota status, recover interrupted
sessions, schedule work, maintain durable Prompt Queues, and support resumable
Jobs and Run Attempts.

This document is the source of truth for architectural boundaries. Read it before
changing structure, ownership, or dependency direction.

The project is **early-stage**. TASK-001 established the skeleton. TASK-002 adds
the provider-independent core domain model and its lifecycle rules. Codex is
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

TASK-001 established the persistence package. TASK-002 defines the domain
objects these tables will eventually store. Those objects live in
`runtime/agentflow/core/domain/` as plain Python. They are not SQLAlchemy
models, and this task does not add mappings or migrations.

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

## 15. Core domain model

TASK-002 defines the shared language for the Scheduler, Prompt Queue, Recovery
Engine, agent adapters, quota recovery, and event history. It does not
implement those engines. The types live in `runtime/agentflow/core/domain/`
and use dataclasses, `StrEnum`, timezone-aware datetimes, and UUIDs.

```text
Job
 │
 ├── WorkflowStep
 │       │
 │       └── QueueItem
 │               │
 │               ├── RunAttempt
 │               └── RunAttempt
 │
 └── AgentSession references execution sessions
```

| Entity | Role |
| --- | --- |
| `Job` | User-level unit of work. Owns workflow steps and execution history. |
| `WorkflowStep` | One logical step inside a job: what should happen, in sequence. |
| `QueueItem` | Durable unit waiting to be dispatched. References a job and a step. |
| `RunAttempt` | One try at executing a queue item. A queue item may have many attempts. |
| `AgentSession` | Generic reference to an external coding-agent session (`adapter_id` + `external_session_id`). |

Three distinctions matter:

- **WorkflowStep != QueueItem.** A step is the description of work (`title`,
  `prompt`, `sequence`). A queue item is the scheduled execution of that work
  (`available_at`, dispatch status). Editing a step does not rewrite items
  already queued.
- **QueueItem != RunAttempt.** A queue item is the durable work order. A run
  attempt is one execution of that order. Quota loss, a network failure, and a
  later success are separate attempts (or a resumed attempt) on the same item.
- **AgentSession != RunAttempt.** A session is the external conversation
  AgentFlow can resume. A run attempt is a single execution that may use that
  session. Closing a session is not the same event as completing an attempt.

`external_session_id` is provider-neutral. Core does not store provider session
field names.

Status enums are separate (`JobStatus`, `WorkflowStepStatus`, `QueueItemStatus`,
`AgentSessionStatus`, `RunAttemptStatus`) even where some names match. Legal
moves live in transition tables. `transition_to(...)` applies them. An illegal
move raises `InvalidStateTransition`. Direct `status` assignment after
construction raises `DomainError`.

Work items (job, step, queue item) share this graph today:

```text
CREATED
   ↓
READY
   ↓
RUNNING
   ├── COMPLETED
   ├── FAILED
   ├── CANCELLED
   ├── PAUSED
   ├── WAITING_USER
   └── WAITING_QUOTA
```

`PAUSED`, `WAITING_USER`, and `WAITING_QUOTA` are recoverable. From
`WAITING_QUOTA` a work item may return to `READY` (dispatch again later) or
`RUNNING` (continue). `COMPLETED`, `FAILED`, and `CANCELLED` are terminal: they
do not transition back to `RUNNING`.

A quota wait is an interruption, not a failure. `WAITING_QUOTA` is not `FAILED`.

`RunAttempt` has no `READY` state. It starts at `CREATED`, enters `RUNNING`, and
may pause or wait. After `WAITING_QUOTA` the same attempt may return to
`RUNNING`. Its `started_at` stays on the original start. `finished_at` is
recorded only for `COMPLETED`, `FAILED`, or `CANCELLED`. `failure_reason` is an
optional provider-neutral string accepted only on the transition into `FAILED`.

`AgentSession` uses `ACTIVE` while the external session is open and `CLOSED`
when it ends cleanly. `WAITING_QUOTA` returns to `ACTIVE` after quota
restoration. That session lifecycle is independent of whether a particular
attempt completed.

Queue items are shaped so later tasks can add `depends_on`, `condition`,
`retry_policy`, `timeout`, and `idempotency_key` as optional fields. Those
behaviors are not implemented here.

---

## Current status (TASK-002)

Implemented:

- monorepo layout (pnpm workspace + Python runtime)
- FastAPI `/health` at the API edge
- React/Electron desktop skeleton
- persistence package placeholder
- adapter package placeholder for Codex
- provider-independent domain model and lifecycle transitions (TASK-002)
- this document, `AGENTS.md`, and Cursor architecture rules

Not implemented (intentionally):

- Codex SDK, login, quota monitoring
- Prompt Queue dispatcher, Scheduler loop, Recovery Engine, workflow DAG behavior
- Claude / Gemini support
- SQLAlchemy mappings and migrations for the domain model
- WebSocket event stream
- cloud sync, accounts, payments, licensing, telemetry, auto-update
