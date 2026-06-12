from typing import TypedDict
from langgraph.graph import StateGraph, END

class WeldingProcurementState(TypedDict):
    spec_data: dict
    is_compliant: bool
    safety_check_required: bool

def validate_welding_specs(state: WeldingProcurementState):
    specs = state.get('spec_data', {})
    is_compliant = 'input_voltage_phase' in specs and 'welding_process_type' in specs
    return {'is_compliant': is_compliant, 'safety_check_required': True}

def perform_safety_review(state: WeldingProcurementState):
    print('Conducting regulatory safety check for welding equipment...')
    return {'safety_check_required': False}

graph = StateGraph(WeldingProcurementState)
graph.add_node('validate', validate_welding_specs)
graph.add_node('safety', perform_safety_review)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()
