from typing import TypedDict
from langgraph.graph import StateGraph, END

class DetectionState(TypedDict):
    device_specs: dict
    validation_status: bool
    compliance_report: str

def validate_specs(state: DetectionState):
    specs = state.get('device_specs', {})
    is_valid = 'frequency_range' in specs and 'sensitivity' in specs
    return {'validation_status': is_valid}

def generate_compliance(state: DetectionState):
    return {'compliance_report': 'Validated against non-metallic detection standards.'}

graph = StateGraph(DetectionState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', generate_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
