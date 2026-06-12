from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    item_name: str
    compliance_checks: List[str]
    is_approved: bool

def validate_certification(state: DentalSupplyState):
    checks = state.get('compliance_checks', [])
    is_approved = 'ISO 13485' in checks and 'FDA' in checks
    return {'is_approved': is_approved}

def finish(state: DentalSupplyState):
    return {'is_approved': state['is_approved']}

graph = StateGraph(DentalSupplyState)
graph.add_node('validate', validate_certification)
graph.add_node('finalizer', finish)
graph.add_edge('validate', 'finalizer')
graph.add_edge('finalizer', END)
graph.set_entry_point('validate')
graph = graph.compile()
