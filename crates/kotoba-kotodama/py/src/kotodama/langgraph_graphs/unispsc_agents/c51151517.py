from langgraph.graph import StateGraph, END
from typing import TypedDict

class ProcurementState(TypedDict):
    api_id: str
    compliance_cleared: bool
    lab_test_required: bool

def validate_api_compliance(state: ProcurementState):
    return {'compliance_cleared': state.get('api_id', '').startswith('API-')}

def perform_quality_check(state: ProcurementState):
    return {'lab_test_required': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_api_compliance)
graph.add_node('quality', perform_quality_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'quality')
graph.add_edge('quality', END)
graph = graph.compile()
