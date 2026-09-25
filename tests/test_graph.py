"""
tests/test_graph.py
 
Covers three things, cheapest/most-isolated first:
 
1. exists_action's routing logic in isolation (no model, no graph).
2. take_action's tool-dispatch logic in isolation (no model, no graph),
   using a monkeypatched dummy tool so these tests don't depend on
   whichever real tools nodes.py currently has (AWS, mock catalog,
   whatever domain it's wired to at the time).
3. The actual compiled graph, with a fake model standing in for
   ChatOpenAI, to prove the HITL gate really pauses execution before
   `action` runs — this is the one guarantee the whole project exists
   to provide, so it gets a dedicated end-to-end test.
 
None of these tests call OpenRouter, OpenAI, or AWS. The fake model
and monkeypatched tool make that unnecessary, and CI should stay that
way — don't replace these with real API calls later.
"""

from typing import cast

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

import src.nodes as node_module
from src.graph import build_graph
from src.nodes import exists_action, take_action
from src.state import AgentState

# ---------------------------------------------------------------------------
# exists_action
# ---------------------------------------------------------------------------

def test_exists_action_true_when_tool_call_present():
    ai_message = AIMessage(
        content="",
        tool_calls = [{"name": "some_tool", "args": {}, "id": "call_1"}],
    )
    
    state = {"message": [HumanMessage(content="hi"), ai_message]}
    assert exists_action(cast(AgentState, state)) is True
    
def test_exists_action_false_when_tool_call_present():
    ai_message = AIMessage(content="No action needed, all clear.")
    state = {"message": [HumanMessage(content="hi"), ai_message]}
    assert exists_action(cast(AgentState, state)) is False
    

# ---------------------------------------------------------------------------
# take_action
# ---------------------------------------------------------------------------

@tool
def dummy_tool(value: str) -> str:
    """A trivial test-only tool that echoes its input.
 
    Args:
        value: Any string.
    """
    return f"echo: {value}"

def test_take_action_executes_known_tool(monkeypatch):
    monkeypatch.setattr(node_module, "TOOLS", [dummy_tool])
    
    ai_message = AIMessage(
        content="",
        tool_calls=[{"name": "dummy_tool", "args": {"value": "hello"}, "id": "call_1"}]
    )
    
    state = {"message": [ai_message]}
    
    result = take_action(state=cast(AgentState, state))
    
    assert "message" in result
    assert len(result["message"]) == 1
    tool_message = result["message"][0]
    assert isinstance(tool_message, ToolMessage)
    assert tool_message.tool_call_id == "call_1"
    assert tool_message.name == "dummy_tool"
    assert "echo: hello" in tool_message.content
    
def test_take_action_handles_unknown_tool(monkeypatch):
    monkeypatch.setattr(node_module, "TOOLS", [dummy_tool])
    
    ai_message = AIMessage(
        content="",
        tool_calls=[{"name": "nonexistent_tool", "args": {"value": "hello"}, "id": "call_1"}]
    )
    
    state = {"message": [ai_message]}
    
    result = take_action(cast(AgentState, state))
    
    tool_message = result["message"][0]
    assert isinstance(tool_message, ToolMessage)
    assert "unknown function call" in str(tool_message.content).lower()
    
    
# ---------------------------------------------------------------------------
# End-to-end: the graph actually pauses before `action`
# ---------------------------------------------------------------------------
 
 
class FakeModel:
    """Stand-in for ChatOpenAI. bind_tools returns self; invoke always
    proposes the same tool call, regardless of input, so the test is
    deterministic without touching a real LLM.
    """
 
    def bind_tools(self, tools):
        return self
 
    def invoke(self, messages):
        return AIMessage(
            content="",
            tool_calls=[
                {"name": "dummy_tool", "args": {"value": "restart"}, "id": "call_1"}
            ],
        )
 
 
def test_graph_pauses_before_action(monkeypatch):
    monkeypatch.setattr(node_module, "TOOLS", [dummy_tool])
 
    fake_model = FakeModel()
    checkpointer = InMemorySaver()
    graph = build_graph(fake_model, checkpointer=checkpointer)
 
    thread = {"configurable": {"thread_id": "test-thread-1"}}
    initial_state = {
        "message": [HumanMessage(content="api-gateway is down")],
        "incident_id": "INC-test",
        "status": "new",
    }
 
    for _ in graph.stream(cast(AgentState, initial_state), cast(RunnableConfig, thread)):
        pass
 
    state = graph.get_state(cast(RunnableConfig, thread))
 
    # The graph must be paused, waiting on the "action" node — this is
    # the entire point of interrupt_before=["action"]. If this fails,
    # the HITL gate is not actually enforcing a human checkpoint.
    assert state.next == ("action",)
 
    # And the proposed action must not have executed yet — no
    # ToolMessage should exist in the conversation until a human
    # resumes the stream.
    assert not any(isinstance(m, ToolMessage) for m in state.values["message"])
 
 
def test_graph_executes_action_after_resume(monkeypatch):
    monkeypatch.setattr(node_module, "TOOLS", [dummy_tool])
 
    fake_model = FakeModel()
    checkpointer = InMemorySaver()
    graph = build_graph(fake_model, checkpointer=checkpointer)
 
    thread = {"configurable": {"thread_id": "test-thread-2"}}
    initial_state = {
        "message": [HumanMessage(content="api-gateway is down")],
        "incident_id": "INC-test-2",
        "status": "new",
    }
 
    for _ in graph.stream(cast(AgentState, initial_state), cast(RunnableConfig, thread)):
        pass
 
    # Simulate a human clicking "Approve": resume with no new input.
    for _ in graph.stream(None, cast(RunnableConfig, thread)):
        pass
 
    state = graph.get_state(cast(RunnableConfig, thread))
    messages = state.values["message"]
 
    assert any(isinstance(m, ToolMessage) for m in messages)
    tool_result = next(m for m in messages if isinstance(m, ToolMessage))
    assert "echo: restart" in tool_result.content