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

from unittest.mock import MagicMock
from typing import Any, cast

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver
from src.state import AgentState

from src.graph import build_graph
from src.nodes import exists_action, take_action
import src.nodes as node_module


# ---------------------------------------------------------------------------
# exists_action
# ---------------------------------------------------------------------------

def test_exists_action_true_when_tool_call_present():
    ai_message = AIMessage(
        content="",
        tool_calls = [{"name": "some_tool", "args": {}, "id": "call_1"}],
    )
    
    state = {"message": [HumanMessage(content="hi"), ai_message]}
    assert exists_action(cast(Any, state)) is True
    
def test_exists_action_false_when_tool_call_present():
    ai_message = AIMessage(content="No action needed, all clear.")
    state = {"message": [HumanMessage(content="hi"), ai_message]}
    assert exists_action(cast(Any, state)) is False
    

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
    assert "echo:hello" in tool_message.content