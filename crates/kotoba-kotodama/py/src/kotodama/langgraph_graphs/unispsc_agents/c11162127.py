from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralProcessState(TypedDict):
    material_id: str
    purity_check: bool
    compliance_docs: List[str]
    validation_score: float

def validate_chemical_purity(state: MineralProcessState):
    # Simulate purity verification logic for extraction chemicals
    is_pure = state.get('validation_score', 0) > 0.95
    return {**state, 'purity_check': is_pure}

def verify_compliance(state: MineralProcessState):
    # Simulate regulatory document verification
    docs = state.get('compliance_docs', [])
    return {**state, 'compliance_docs': docs + ['MSDS_VERIFIED']}

def build_graph():
    workflow = StateGraph(MineralProcessState)
    workflow.add_node('purity_check', validate_chemical_purity)
    workflow.add_node('compliance_check', verify_compliance)
    workflow.set_entry_point('purity_check')
    workflow.add_edge('purity_check', 'compliance_check')
    workflow.add_edge('compliance_check', END)
    return workflow.compile()

graph = build_graph()
