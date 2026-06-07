from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_result: bool
    compliance_report: str

def validate_medical_device(state: ProcurementState):
    device_specs = state.get('spec_data', {})
    is_valid = all(key in device_specs for key in ['ISO_10993', 'Sterility_Batch'])
    return {'validation_result': is_valid, 'compliance_report': 'Passed' if is_valid else 'Failed: Missing ISO cert'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_medical_device)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
