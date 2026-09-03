# HITL-Incident-Engine

A Human-in-the-Loop incident response engine. Alerts come in, an agent proposes
what to do about them, and nothing state-changing ever runs until a human
approves it. Every step is logged so the whole flow is auditable after the fact.

## Why

Fully autonomous incident response is risky — an agent that can restart
services or close tickets on its own can make an incident worse. This project
keeps a human in the loop for any action with real-world consequences, while
still automating the tedious parts: normalizing alerts, drafting a diagnosis,
and recording what happened.

## Project layout

```
config/
  settings.yaml / .env.example   # thresholds, API keys, DB path, Slack/webhook tokens

src/
  __init__.py
  models.py            # Incident, Severity, ApprovalStatus data classes/enums
  ingestion.py         # normalizes incoming alerts into an Incident object
  triage.py            # agent/rules logic: reads Incident, proposes diagnosis + action
  hitl_gate.py         # the approval layer — pauses, asks a human, records the decision
  actions.py           # the actual remediation functions (restart_service, notify, etc.)
  audit.py             # append-only log of every step (who decided what, when)
  db.py                # persistence layer (sqlite/postgres) for incidents + approvals
  main.py / cli.py     # entrypoint that wires everything together
  interfaces/
    slack_bot.py        # or api.py / cli_interface.py — however humans interact with it

tests/
  test_ingestion.py
  test_triage.py
  test_hitl_gate.py
  test_actions.py

.github/workflows/
  ci.yml               # lint + pytest on push/PR
```

## Workflow

The pipeline runs in a fixed order, and only one file (`hitl_gate.py`) is
allowed to unlock execution.

1. **Ingestion** (`ingestion.py`)
   Receives a raw alert — from a webhook, CLI arg, or test fixture — and
   converts it into a standard `Incident` object (id, title, severity,
   service, timestamp, status = `new`). This is the only place that deals
   with messy external input.

2. **Triage** (`triage.py`)
   Takes the `Incident` and decides what *should* happen, e.g. "restart
   order-worker" or "escalate to on-call." This stage only **proposes** —
   it never executes. Output: an `ActionProposal` (action name, target,
   reasoning, confidence score).

3. **HITL gate** (`hitl_gate.py`)
   The core of the project. It:
   - Writes a pending approval record via `db.py`.
   - Surfaces the proposal to a human through whichever `interfaces/`
     module is active (Slack message, CLI prompt, API endpoint returning
     `pending`).
   - Blocks or polls until the human approves, edits, or rejects.
   - Returns a final `ApprovedAction` or `RejectedAction`.

4. **Actions** (`actions.py`)
   Runs only once `hitl_gate.py` returns an `ApprovedAction`. Each function
   here is a discrete, auditable operation (`restart_service(name)`,
   `file_ticket(summary)`, etc.), ideally with a dry-run mode.

5. **Audit** (`audit.py`)
   Called at every transition — ingested → triaged → pending approval →
   approved/rejected → executed — and writes an immutable record. This is
   what makes the system audit-worthy rather than just an agent script.

6. **Persistence** (`db.py`)
   Backs both the incident store and the approvals table. Kept thin (CRUD
   only) so `hitl_gate.py` and `audit.py` don't duplicate storage logic.

7. **Entrypoint** (`main.py` / `cli.py`)
   The only file that imports everything and wires the pipeline:
   `ingest → triage → hitl_gate → actions → audit`, in that order, catching
   exceptions at each stage so a failure doesn't silently skip the human
   check.

8. **Interfaces** (`interfaces/`)
   Decoupled from core pipeline logic — they call `hitl_gate`'s public
   functions (`get_pending_approvals()`, `submit_decision(id, approve/reject)`)
   so you can swap Slack for a web dashboard later without touching the
   pipeline.

9. **CI** (`.github/workflows/ci.yml`)
   Runs `pytest tests/` plus a linter on every push. The HITL gate logic
   especially should stay well tested — a bug there is the one failure mode
   this whole project exists to prevent.

## Design rule

Nothing in `actions.py` should ever be callable directly from `triage.py`.
The only path to execution runs through `hitl_gate.py`. That boundary is the
whole point of the project.

## Status

Early scaffold — core modules and pipeline wiring not yet implemented.