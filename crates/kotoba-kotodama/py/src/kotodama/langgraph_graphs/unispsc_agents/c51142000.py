from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    batch_id: str
    compliance_cleared: bool
    purity_level: float

def validate_purity(state: DrugProcurementState):
    state['compliance_cleared'] = state['purity_level'] >= 0.99
    return state

def route_by_compliance(state: DrugProcurementState):
    return 'process' if state['compliance_cleared'] else 'reject'

graph = StateGraph(DrugProcurementState)
graph.add_node('validate', validate_purity)
graph.add_edge('start', 'validate')
graph.add_conditional_edges('validate', route_by_compliance, {'process': END, 'reject': END})
graph.set_entry_point('validate')

graph = graph.compile()
