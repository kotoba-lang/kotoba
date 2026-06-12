from typing import TypedDict
from langgraph.graph import StateGraph, END

class SoftwareState(TypedDict):
    license_key: str
    compatibility_check: bool
    is_compliant: bool

def validate_license(state: SoftwareState):
    return {"compatibility_check": len(state.get("license_key", "")) > 10}

def check_compliance(state: SoftwareState):
    return {"is_compliant": state.get("compatibility_check", False)}

graph = StateGraph(SoftwareState)
graph.add_node("validate", validate_license)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
