from typing import TypedDict
from langgraph.graph import StateGraph, END

class IndustrialSoftwareState(TypedDict):
    license_key: str
    compatibility_check: bool
    security_audit_passed: bool

def validate_license(state: IndustrialSoftwareState):
    return {"license_key": "VALIDATED"}

def perform_security_scan(state: IndustrialSoftwareState):
    return {"security_audit_passed": True}

graph = StateGraph(IndustrialSoftwareState)
graph.add_node("validate", validate_license)
graph.add_node("security", perform_security_scan)
graph.add_edge("validate", "security")
graph.add_edge("security", END)
graph.set_entry_point("validate")
graph = graph.compile()
