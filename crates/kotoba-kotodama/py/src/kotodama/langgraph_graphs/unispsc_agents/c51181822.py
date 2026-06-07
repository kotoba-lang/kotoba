from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    api_name: str
    purity_check: bool
    compliance_docs: List[str]
    approved: bool

def validate_purity(state: ProcurementState):
    # Simulate chemical analysis validation logic
    state['purity_check'] = True if state.get('purity_percentage', 0) >= 99.0 else False
    return state

def verify_compliance(state: ProcurementState):
    # Verify GMP and Drug Master File documentation
    state['approved'] = state['purity_check'] and len(state['compliance_docs']) > 0
    return state

graph = StateGraph(ProcurementState)
graph.add_node("purity", validate_purity)
graph.add_node("compliance", verify_compliance)
graph.set_entry_point("purity")
graph.add_edge("purity", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
