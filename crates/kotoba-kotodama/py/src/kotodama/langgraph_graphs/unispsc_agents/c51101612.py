from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    compliance_checked: bool
    coa_validated: bool

def check_compliance(state: ProcurementState):
    # Business logic for pharma grade verification
    return {"compliance_checked": True}

def validate_coa(state: ProcurementState):
    # Logic to verify CoA against pharmacopeia
    return {"coa_validated": True}

graph = StateGraph(ProcurementState)
graph.add_node("compliance", check_compliance)
graph.add_node("coa_validation", validate_coa)
graph.set_entry_point("compliance")
graph.add_edge("compliance", "coa_validation")
graph.add_edge("coa_validation", END)

graph = graph.compile()
