from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    commodity_code: str
    spec_compliance: bool
    inspection_result: dict
    approved: bool

def validate_specs(state: ProcurementState) -> ProcurementState:
    # Logic to validate commodity against spec fields
    state['spec_compliance'] = True
    return state

def perform_inspection(state: ProcurementState) -> ProcurementState:
    # Logic to perform automated inspection steps
    state['inspection_result'] = {'status': 'passed', 'details': 'validated_tolerance'}
    state['approved'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('inspect', perform_inspection)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph = graph.compile()
