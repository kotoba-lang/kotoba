from typing import TypedDict
from langgraph.graph import StateGraph, END

class RegulatorState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_risk: str

def validate_specs(state: RegulatorState) -> dict:
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['control_accuracy', 'calibration_certificate'])
    return {'validation_passed': is_valid, 'compliance_risk': 'low' if is_valid else 'high'}

def process_workflow(state: RegulatorState) -> dict:
    print(f'Processing calibration for accuracy: {state.get('spec_data').get('control_accuracy')}')
    return {'compliance_risk': 'verified'}

graph = StateGraph(RegulatorState)
graph.add_node('validator', validate_specs)
graph.add_node('processor', process_workflow)
graph.set_entry_point('validator')
graph.add_edge('validator', 'processor')
graph.add_edge('processor', END)
graph = graph.compile()
