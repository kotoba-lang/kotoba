from typing import TypedDict
from langgraph.graph import StateGraph, END

class PathologyRoomState(TypedDict):
    room_specs: dict
    compliance_report: dict

def validate_biosecurity(state: PathologyRoomState):
    # Simulate regulatory validation logic
    return {"compliance_report": {"status": "verified"}}

def finalize_design(state: PathologyRoomState):
    return {"compliance_report": {"finalized": True}}

graph = StateGraph(PathologyRoomState)
graph.add_node("validate", validate_biosecurity)
graph.add_node("finalize", finalize_design)
graph.set_entry_point("validate")
graph.add_edge("validate", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
