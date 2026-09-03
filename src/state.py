from typing import Annotated, TypedDict
from uuid import uuid4

from langchain_core.messages import AnyMessage # type: ignore

def reduce_messages(left: list[AnyMessage], right: list[AnyMessage]) -> list[AnyMessage]:
    """Merge new messages into existing ones.
 
    - Assigns an id to any incoming message that doesn't have one.
    - If an incoming message shares an id with an existing message,
      it replaces that message in place (used when a human edits a
      proposed tool call before approving it).
    - Otherwise, the message is appended.
    """
    for message in right:
        if not message.id:
            message.id = str(uuid4())
            
    merged = left.copy()
    for message in right:
        for i, existing in enumerate(merged):
            if existing.id == message.id:
                merged[i]= message
                break
        else:
            merged.append(message)

    return merged
    
    
class AgentState(TypedDict):
    """State carried through the incident-triage graph.
 
    messages:
        Full conversation/tool-call history for this incident thread.
        Annotated with `reduce_messages` so edits replace rather than
        duplicate entries.
    incident_id:
        Identifier for the incident this thread represents. Set once
        at ingestion and never overwritten.
    status:
        Coarse lifecycle marker for the incident, useful for audit
        logging and for filtering "pending approval" incidents in the
        interface layer. One of: "new", "triaged", "pending_approval",
        "approved", "rejected", "resolved".
    """
    
    message: Annotated[list[AnyMessage], reduce_messages]
    incident_id: str
    status: str
        

    
    