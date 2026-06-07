from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class DictProcState(TypedDict):
    device_id: str
    spec_check: bool
    compliance_verified: bool

def validate_specs(state: DictProcState):
    # Logic to verify internal dictionary storage requirements
    return {"spec_check": True}

def check_compliance(state: DictProcState):
    # Logic to verify electrical safety and regional standards
    return {"compliance_verified": True}

graph = StateGraph(DictProcState)
graph.add_node("validate", validate_specs)
graph.add_node("compliance", check_compliance)
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph.set_entry_point("validate")
graph = graph.compile()
