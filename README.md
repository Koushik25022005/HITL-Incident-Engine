# HITL-Incident-Engine

A Human-in-the-Loop incident response engine built on LangGraph. An agent
proposes what to do about an incident (restart a service, file a retro), but
nothing state-changing ever executes until a human approves it. The graph's
checkpointer keeps a full history of every state transition, so the whole
flow is auditable after the fact.

## Why

Fully autonomous incident response is risky — an agent that can restart
services or close tickets on its own can make an incident worse. This
project keeps a human in the loop for any action with real-world
consequences, using LangGraph's `interrupt_before` mechanism to pause
execution before anything destructive runs.

## Project layout

```
.github/workflows/
  ci.yml              # lint + pytest on push/PR

config/
  settings.py         # model name, API key references, checkpointer DB path

src/
  __init__.py
  state.py            # AgentState schema + custom message reducer
  nodes.py            # tools + node functions (call_model, exists_action, take_action)
  graph.py            # StateGraph assembly, compile(checkpointer=..., interrupt_before=["action"])

tests/
  __init__.py
  test_graph.py       # routing logic + interrupt behavior

app.py                # entrypoint: thread loop, streaming, approval prompt
requirements.txt
.env                  # OPENAI_API_KEY, etc. (not committed)
```

## Workflow

The pipeline is a LangGraph graph with two nodes, `llm` and `action`, and a
single compile-time setting that enforces the human checkpoint.

1. **State** (`src/state.py`)
   Defines `AgentState`: a `messages` list (using a custom reducer that
   *replaces* a message when a human edits it, rather than duplicating it),
   plus `incident_id` and `status` for tracking the incident's lifecycle.

2. **LLM node** (`src/nodes.py::make_call_model`)
   Takes the current state, prepends the system prompt, and invokes the
   model with tools bound (`lookup_service`, `restart_service`,
   `file_incident_retro`). The model's response — plain text or a proposed
   tool call — is appended to `messages`.

3. **Routing** (`src/nodes.py::exists_action`)
   Checks whether the last message contains a tool call. If so, the graph
   routes to the `action` node; if not, the graph ends.

4. **HITL gate** (`src/graph.py`)
   The graph is compiled with:
   ```python
   app = graph.compile(checkpointer=checkpointer, interrupt_before=["action"])
   ```
   This is the entire approval mechanism — execution always pauses
   immediately before the `action` node runs, regardless of what the
   proposed tool call is. No action reaches `take_action` without this
   pause happening first.

5. **Action node** (`src/nodes.py::take_action`)
   Only reached after the graph resumes past the interrupt. Executes the
   proposed tool call(s) and appends the results as `ToolMessage`s.

6. **Checkpointer / persistence** (`config/settings.py` + `src/graph.py`)
   A `SqliteSaver` (or equivalent) backs the graph, keyed by `thread_id`.
   This is what allows an incident to sit "pending approval" indefinitely
   and be resumed later, potentially from a different process.

7. **Approval loop** (`app.py`)
   The entrypoint runs the graph for a given thread, then loops:
   ```python
   while app.get_state(thread).next:
       decision = input("proceed? ")
       if decision != "y":
           break
       for event in app.stream(None, thread):
           ...
   ```
   A human can also inspect (`get_state`) and edit (`update_state`) the
   proposed tool call before approving it — e.g. correcting a service name
   — before resuming the stream.

8. **Audit trail**
   `app.get_state_history(thread)` returns every state snapshot for an
   incident, in order — ingestion, triage, pause, approval/edit, execution.
   No separate audit log is needed; this comes from the checkpointer for
   free and can be surfaced via a CLI command or API endpoint.

9. **CI** (`.github/workflows/ci.yml`)
   Runs `pytest tests/` on every push. `tests/test_graph.py` should cover
   `exists_action`'s routing and confirm that the compiled graph actually
   halts at `interrupt_before=["action"]` before any tool executes.

## Design rule

No tool call in `take_action` should ever run without the graph first
pausing at the `interrupt_before` boundary. That pause is the entire point
of the project — it's what turns an autonomous agent into a human-approved
one.

## Status

Core scaffold in place (`state.py`, `nodes.py`); `graph.py`, `app.py`, and
tests are the next pieces to fill in.