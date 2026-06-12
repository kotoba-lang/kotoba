from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_result: bool
    approved: bool

def validate_material(state: ProcurementState):
    specs = state.get('spec_data', {})
    # Check for heat resistance compliance
    is_valid = specs.get('heat_resistance_rating', 0) >= 200
    return {'validation_result': is_valid}

def approval_step(state: ProcurementState):
    return {'approved': state['validation_result']}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_material)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
