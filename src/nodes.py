"""Node functions for the incident-triage graph, plus the tools an
incident commander agent is allowed to call.
 
Mirrors the `call_openai` / `exists_action` / `take_action` methods
of the `Agent` class in Lesson 5, but split out as standalone
functions so `graph.py` can wire them into a `StateGraph` without
needing a wrapping class.
 
Replace the placeholder tool implementations (`lookup_service`,
`restart_service`, `file_incident_retro`) with real calls into your
infrastructure/ticketing systems when you're ready — the node
functions below don't need to change when you do."""
    
    
from langchain_core.messages import SystemMessage, ToolMessage # type: ignore
from langchain_core.tools import tool # type: ignore

from src.state import AgentState

# ---------------------------------------------------------------------------
# Tools
#
# NOTE: only *read-only* or already-approved tools should ever be reachable
# from `take_action`. Anything destructive (restart_service, closing an
# incident) must only run after the graph has paused at the HITL gate
# (interrupt_before=["action"] in graph.py) and a human has approved it.
# ---------------------------------------------------------------------------

@tool
def lookup_service(service_name: str) -> dict:
    """Return known info (region, replica count, runbook) for a service.
 
    Args:
        service_name: Logical service name, e.g. "api-gateway".
    """
    catalog = {
        "api-gateway": {"region": "us-west-2", "replica_count": 12, "runbook": "rb/api-gateway"},
        "order-worker": {"region": "us-west-2", "replica_count": 6, "runbook": "rb/order-worker"},
        "user-profile": {"region": "us-west-2", "replica_count": 4, "runbook": "rb/user-profile"}
    }
    svc = catalog.get(service_name)
    if not svc:
        raise ValueError(f"Service not found: {service_name}")
    return svc


@tool
def restart_service(service_name: str) -> str:
    """Restart a production service. Destructive — must go through the HITL gate.
 
    Args:
        service_name: Logical service name to restart.
    """
    return f"Restarted '{service_name}' restarted successfully."


@tool
def file_incident(incident_id: str, summary: str, priority: str) -> str:
    # Replace with a real orchestration call (kubectl, systemctl, etc.) or a ticketing system API call.
    return f"Incident filed with ID: {incident_id}"


TOOLS = [lookup_service, restart_service, file_incident]

system_prompt = """You are an incident commander. Use the availoabel tools to investigate and remediate production
Only propose one action at a time when the action is indestructive (e.g. restarting a service) - a human will review it
before it is executed. Before recommending the restart, look up service information. Once the incident is resolved, file a retrospective."""


# ---------- Grpah Node Functions -------------

def make_call_model(model):
    """Bind tools to the model and return the `llm` node function.
 
    Mirrors `Agent.call_openai` from the notebook. Returned as a closure
    so `graph.py` can supply the configured model without this module
    needing to know about `config/settings.py`.
    """
    
    model_with_tools = model.bind_toold(TOOLS)
    
    def call_model(state: AgentState) -> dict:
        messages = state["message"]
        messages = [SystemMessage(content=system_prompt)] + messages
        response = model_with_tools.invoke(messages)
        return {"message": [response]}
    
    return call_model
