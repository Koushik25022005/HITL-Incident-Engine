"""
app.py
 
Streamlit interface for the HITL Incident Engine.
 
Responsibilities:
- Start/resume an incident "thread" (one LangGraph thread per incident).
- Run the agent up to the point where it proposes a tool call.
- Show the proposed action and let a human approve, edit, or reject it
  before anything destructive executes (the interrupt_before=["action"]
  gate in src/graph.py is what actually enforces the pause).
- Display the running conversation and a full audit trail via
  get_state_history.
 
Run with:
    streamlit run app.py
"""
import ast
import uuid
import sqlite3
from typing import Any
from langgraph.checkpoint.sqlite import SqliteSaver # type: ignore
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage # type: ignore
from langchain_core.runnables.config import RunnableConfig


from config.settings import CHECKPOINT_DB_PATH
from src.graph import build_graph
from src.nodes import build_model

import streamlit as st # type: ignore

st.set_page_config(page_title="HITL Incident Engine", layout="wide")

# ---------------------------------------------------------------------------
# One-time setup: model, checkpointer, compiled graph.
# Cached so Streamlit doesn't rebuild these on every rerun/interaction.
# ---------------------------------------------------------------------------

@st.cache_resource
def get_app():
    model = build_model()
    conn = sqlite3.connect(CHECKPOINT_DB_PATH, check_same_thread=False)
    checkpointer=SqliteSaver(conn)
    return build_graph(model, checkpointer=checkpointer)


graph = get_app()

# ---------------------------------------------------------------------------
# Session state: which incident thread we're on.
# Each incident gets its own thread_id so its history/checkpoints don't mix
# with other incidents.
# ---------------------------------------------------------------------------

if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
    
if "incident_id" not in st.session_state:
    st.session_state.incident_id = None
    
    
def start_new_incident(description: str):
    thread_id = str(uuid.uuid4());
    incident_id = f"INC-{thread_id[:8]}"
    st.session_state.thread_id = thread_id
    st.session_state.incident_id = incident_id
    
    thread: RunnableConfig = {"configurable": {"thread_id": thread_id}}
    initial_state: Any = {
        "message": [HumanMessage(content=description)],
        "incident_id": incident_id,
        "status": "new"
    }
    
    for _ in graph.stream(initial_state, thread):
        pass

# ---------------------------------------------------------------------------
# Sidebar: start a new incident.
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("New Incident")
    description = st.text_area(
        "Describe the incident",
        placeholder="api-gateway is returning 500s in us-west-2 since 14:02 UTC",
    )
    
    if st.button("Start triage", type="primary", disabled=not description):
        start_new_incident(description)
        st.rerun()
        
st.divider()
st.caption(f"Current Thread: `{st.session_state.thread_id or '-'}`")
st.caption(f"Incident ID: `{st.session_state.incident_id or '-'}`")
        
# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------

st.title("HITL Incident Engine")

if not st.session_state.thread_id:
    st.info("Start a new incident from the sidebar to begin.")
    st.stop()
    
thread: RunnableConfig = {"configurable": {"thread_id": st.session_state.thread_id}}
state = graph.get_state(thread)
 
# --- Conversation so far -----------------------------------------------
st.subheader("Conversation")
for msg in state.values.get("message", []):
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"):
            st.write(msg.content)
            
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"):
            if msg.content:
                st.write(msg.content)
            for call in getattr(msg, "tool_calls", []):
                st.caption(f"Proposed tool call: `{call['name']}` - `{call['args']}`")
    
    elif isinstance(msg, ToolMessage):
        with st.chat_message("assistant"):
            st.caption(f"Tool result ({msg.name}): {msg.content}")
        

# --- Approval gate --------------------------------------------------------
# `state.next` is non-empty only when the graph is paused — i.e. it's about
# to run a node in `interrupt_before` (our "action" node) and is waiting.

if state.next:
    st.subheader("Pending Approval.......")
    last_message = state.values["message"][-1]
    tool_calls = getattr(last_message, "tool_calls", [])
    
    for call in tool_calls:
        st.warning(f"Agent wants to call **`{call['name']}`** with **`{call['args']}`**")
        
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("Approve", type="primary"):
            for _ in graph.stream(None, thread):
                pass
            st.rerun()
    
    with col2:
        with st.popover("Edit Arguments"):
            if tool_calls:
                call = tool_calls[0]
                new_args_raw = st.text_area(
                    "Args (Python dict literal)",
                    value=str(call["args"]),
                    key=f"edit_{call['id']}"
                )
                
                if st.button("Save edit and approve"):
                    edited_message = last_message.model_copy(deep=True)
                    edited_message.tool_calls[0]["args"] = ast.literal_eval(new_args_raw)
                    
                    
                    graph.update_state(thread, {"message": [edited_message]})
                    for _ in graph.stream(None, thread):
                        pass
                    st.rerun()
        
    with col3:
            if st.button("Reject"):
                rejection = ToolMessage(
                    tool_call_id=tool_calls[0]["id"] if tool_calls else "n/a",
                    name="rejection",
                    content="Human rejected this action."
                )
                graph.update_state(thread, {"message": [rejection], "status": "rejected"})
                st.rerun()
                
# --------- Audit trail -----------------------

with st.expander("Audit trail (full state history)"):
    for snapshot in graph.get_state_history(thread):
        st.text(
            f"step={(snapshot.metadata or {}).get('step') or {}} "
            f"next={snapshot.next} "
            f"message={len(snapshot.values.get('message', []))}"
        )
    