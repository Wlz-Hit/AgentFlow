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

TASK-001 established the persistence package. TASK-002 defined the domain
objects. TASK-003 maps those objects to SQLite through repository ports,
SQLAlchemy adapters, and Alembic migrations. Domain dataclasses remain separate
from ORM models.

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

Domain reconstruction rejects inconsistent timestamps (`updated_at` before
`created_at`, `available_at` before `created_at`, and RunAttempt timing that
contradicts status). Transitions may not move lifecycle timestamps backwards.
`RunAttempt` requires `started_at` for every status except `CREATED` and
pre-start `CANCELLED`, requires `finished_at` for terminal statuses, and
rejects `failure_reason` unless status is `FAILED`.

## 16. Durable persistence

TASK-003 makes the domain model restart-safe:

```text
Domain Core
    ↓
Repository Port
    ↓
SQLAlchemy Repository
    ↓
SQLite
```

### Repository ports

Protocols live in `runtime/agentflow/core/ports/repositories.py`:

- `JobRepository`
- `WorkflowStepRepository`
- `QueueItemRepository`
- `AgentSessionRepository`
- `RunAttemptRepository`
- `UnitOfWork`

Core depends on these interfaces. SQLAlchemy implementations live only under
`runtime/agentflow/persistence/`.

### Domain ↔ ORM mapping

ORM rows (`JobRow`, …) are separate from domain dataclasses. Mappers in
`persistence/mappers.py` convert both ways. Repository methods return domain
entities; ORM objects do not escape the persistence package.

### Transaction boundary

`SqlAlchemyUnitOfWork` binds every repository to one SQLAlchemy session.
Application code calls `commit()` to persist a batch of changes atomically.
Leaving the context without commit, or exiting with an exception, rolls back.
This is intentionally small: one UoW per operation, not a framework.

### UUID representation

UUIDs are stored as canonical 36-character strings
(`xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`). Domain code keeps using `uuid.UUID`.
Adapters convert at the boundary via `UuidAsString`.

### Enum representation

Status columns store stable string values (`running`, `waiting_quota`,
`completed`, …). Loading reconstructs the correct domain `StrEnum`. Ordinal
positions are never persisted.

### UTC timestamp strategy

SQLite datetime affinity does not preserve timezone. Timestamps are stored as
ISO-8601 UTC strings (for example `2026-09-22T08:00:00+00:00`) through
`UtcDateTimeAsIso`. After save → close → reopen → load, domain objects still
expose timezone-aware UTC datetimes.

### SQLite foreign keys

Foreign-key enforcement is enabled with `PRAGMA foreign_keys=ON` on every
connection. Relationships:

- `workflow_steps.job_id` → `jobs.id`
- `queue_items.job_id` → `jobs.id`
- `queue_items.workflow_step_id` → `workflow_steps.id`
- `run_attempts.queue_item_id` → `queue_items.id`
- `run_attempts.agent_session_id` → `agent_sessions.id`

### Constraints and the active RunAttempt rule

Notable uniqueness constraints:

- `(job_id, sequence)` on workflow steps and on queue items
- `(adapter_id, external_session_id)` on agent sessions
- `(queue_item_id, attempt_number)` on run attempts

A queue item may have many historical attempts, but **at most one non-terminal
RunAttempt** at a time. Quota interruption resumes the same attempt
(`RUNNING → WAITING_QUOTA → RUNNING`). Creating a replacement attempt requires
the previous one to become terminal (`CANCELLED` or `FAILED`). Enforcement:

1. Application check in `SqlAlchemyRunAttemptRepository.save`
2. Partial unique index `uq_run_attempts_one_active_per_queue_item` on
   `queue_item_id` where `status NOT IN ('completed', 'failed', 'cancelled')`

### Restart recovery implications

Process stop/start must not lose or corrupt domain state. Durable writes go
through the UoW commit path. Reloaded entities re-run domain validation, so
corrupt rows fail loudly instead of silently becoming invalid in-memory
objects. Scheduler and recovery engines (not yet implemented) will open a UoW,
load entities, apply domain transitions, and commit.

Schema changes ship as Alembic revisions under `runtime/alembic/versions/`.
`metadata.create_all()` is not the production migration strategy.

---

## Current status (TASK-003)

Implemented:

- monorepo layout (pnpm workspace + Python runtime)
- FastAPI `/health` at the API edge
- React/Electron desktop skeleton
- provider-independent domain model and lifecycle transitions (TASK-002)
- domain invariant hardening for timestamps and RunAttempt consistency
- repository ports, SQLAlchemy adapters, Alembic domain migration (TASK-003)
- this document, `AGENTS.md`, and Cursor architecture rules

Not implemented (intentionally):

- Codex SDK, login, quota monitoring
- Prompt Queue dispatcher, Scheduler loop, Recovery Engine, workflow DAG behavior
- Claude / Gemini support
- WebSocket event stream
- cloud sync, accounts, payments, licensing, telemetry, auto-update
