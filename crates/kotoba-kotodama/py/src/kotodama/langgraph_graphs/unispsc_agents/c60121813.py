from typing import TypedDict
from langgraph.graph import StateGraph, END

class InkState(TypedDict):
    ink_type: str
    viscosity_check: bool
    safety_compliant: bool

def validate_viscosity(state: InkState):
    return {"viscosity_check": True if state.get("ink_type") else False}

def check_compliance(state: InkState):
    return {"safety_compliant": True}

graph = StateGraph(InkState)
graph.add_node("validate_viscosity", validate_viscosity)
graph.add_node("check_compliance", check_compliance)
graph.set_entry_point("validate_viscosity")
graph.add_edge("validate_viscosity", "check_compliance")
graph.add_edge("check_compliance", END)
graph = graph.compile()
