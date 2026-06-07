from typing import TypedDict
from langgraph.graph import StateGraph, END

class DirectorySoftwareState(TypedDict):
    software_name: str
    compliance_report: dict
    approved: bool

def validate_protocols(state: DirectorySoftwareState):
    # Business logic for protocol compliance
    return {"approved": True, "compliance_report": {"status": "passed"}}

def finalize_procurement(state: DirectorySoftwareState):
    return {"approved": True}

graph = StateGraph(DirectorySoftwareState)
graph.add_node("validate_protocols", validate_protocols)
graph.add_node("finalize", finalize_procurement)
graph.set_entry_point("validate_protocols")
graph.add_edge("validate_protocols", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
