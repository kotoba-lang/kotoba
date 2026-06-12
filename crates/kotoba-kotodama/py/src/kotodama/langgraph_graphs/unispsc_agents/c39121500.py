from langgraph.graph import StateGraph, END
from typing import TypedDict

class ProcurementState(TypedDict):
    spec_data: dict
    validation_status: str

def validate_electrical_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    if 'Rated Voltage' in specs and 'UL/CE Certification' in specs:
        return {'validation_status': 'COMPLIANT'}
    return {'validation_status': 'PENDING_REVIEW'}

def route_by_validation(state: ProcurementState):
    return state['validation_status']

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_electrical_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
