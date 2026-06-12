from typing import TypedDict
from langgraph.graph import StateGraph, END

class MillingMachineState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_specs(state: MillingMachineState):
    specs = state.get('spec_data', {})
    errors = []
    if specs.get('positioning_accuracy', 0) > 0.01:
        errors.append('Accuracy tolerance too high for gantry standard.')
    return {'validation_results': errors, 'is_compliant': len(errors) == 0}

def route_by_compliance(state: MillingMachineState):
    return 'end' if state['is_compliant'] else 'manual_review'

graph = StateGraph(MillingMachineState)
graph.add_node('validate', validate_specs)
graph.add_node('manual_review', lambda x: x)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance, {'end': END, 'manual_review': 'manual_review'})
graph.add_edge('manual_review', END)
graph = graph.compile()
