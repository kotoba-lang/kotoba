from langgraph.graph import StateGraph, END
from typing import TypedDict
class ProcurementState(TypedDict):
    item_name: str
    spec_verified: bool
    compliance_score: float
def validate_specs(state: ProcurementState):
    state['spec_verified'] = True
    return state
def check_compliance(state: ProcurementState):
    state['compliance_score'] = 1.0
    return state
graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
