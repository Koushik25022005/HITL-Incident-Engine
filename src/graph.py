from langgraph.graph import StateGraph, END # type: ignore

from src.state import AgentState
from src.nodes import make_call_model, exists_action, take_action



def build_graph(model, tools, checkpointer=None):
    """Build the incident-triage graph, wiring in the model and tools
    without the graph needing to know about `config/settings.py`.
    """

    
    call_model = make_call_model(model)
    
    graph = StateGraph(AgentState)
    graph.add_node("call_model", call_model)
    graph.add_node("action", take_action)
    graph.add_conditional_edge("llm", exists_action, {True: "take_action", False: END})
    graph.add_edge("call_model", "action")
    graph.set_entry_point("call_model")
    
    return graph.compile(
        checkpointer = checkpointer,
        interrupt_before=["action"]
    )