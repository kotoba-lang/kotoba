from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    purity: float
    gmp_verified: bool
    approved: bool

def validate_purity(state: DrugProcurementState):
    state['approved'] = state.get('purity', 0) >= 99.9
    return state

def check_compliance(state: DrugProcurementState):
    if not state.get('gmp_verified'):
        state['approved'] = False
    return state

graph = StateGraph(DrugProcurementState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("validate")
graph.add_edge("validate", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
