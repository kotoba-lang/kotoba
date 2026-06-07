from typing import TypedDict
from langgraph.graph import StateGraph, END

class VisionStandState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: VisionStandState):
    specs = state.get('spec_data', {})
    compliant = 'height_adjustment_range' in specs and 'medical_device_certification_iso13485' in specs
    return {'is_compliant': compliant, 'validation_log': ['Specs checked']}

def route_by_compliance(state: VisionStandState):
    return 'compliant' if state['is_compliant'] else 'non_compliant'

graph = StateGraph(VisionStandState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
