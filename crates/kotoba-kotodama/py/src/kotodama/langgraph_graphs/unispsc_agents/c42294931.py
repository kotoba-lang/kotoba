from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_medical_device(state: ProcurementState):
    device_specs = state.get('spec_data', {})
    required = ['sterility', 'iso_code']
    valid = all(key in device_specs for key in required)
    return {'validation_passed': valid}

def process_clinical_reqs(state: ProcurementState):
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_medical_device)
graph.add_node('process', process_clinical_reqs)
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph.set_entry_point('validate')
graph = graph.compile()
