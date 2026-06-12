from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_id: str
    compliance_cleared: bool
    is_controlled: bool

def check_compliance(state: ProcurementState):
    # Simulate regulatory API check for Secobarbital
    state['is_controlled'] = True
    state['compliance_cleared'] = True
    return state

def finalize_order(state: ProcurementState):
    return {"status": "ready_for_purchase"}

graph = StateGraph(ProcurementState)
graph.add_node("compliance_check", check_compliance)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("compliance_check")
graph.add_edge("compliance_check", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
