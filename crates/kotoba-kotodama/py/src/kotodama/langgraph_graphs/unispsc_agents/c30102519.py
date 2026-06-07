from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    is_valid = all(key in specs for key in ['tensile_strength', 'material_type'])
    return {'validation_passed': is_valid}

def approval_step(state: ProcurementState):
    print('Proceeding to procurement approval...')
    return {'validation_passed': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
