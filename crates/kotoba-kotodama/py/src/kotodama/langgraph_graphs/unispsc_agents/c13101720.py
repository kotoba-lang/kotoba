from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class CatalystState(TypedDict):
    material_spec: dict
    compliance_checks: Sequence[str]
    approval_status: str

def validate_catalyst_purity(state: CatalystState):
    spec = state.get('material_spec', {})
    if spec.get('purity', 0) >= 99.9:
        return {'compliance_checks': ['purity_passed'], 'approval_status': 'pending'}
    return {'compliance_checks': ['purity_failed'], 'approval_status': 'rejected'}

def process_safety_review(state: CatalystState):
    return {'compliance_checks': ['safety_review_cleared'], 'approval_status': 'approved'}

graph = StateGraph(CatalystState)
graph.add_node('validate_purity', validate_catalyst_purity)
graph.add_node('safety_review', process_safety_review)
graph.set_entry_point('validate_purity')
graph.add_edge('validate_purity', 'safety_review')
graph.add_edge('safety_review', END)
graph = graph.compile()
