from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ConveyorState(TypedDict):
    specs: dict
    validation_passed: bool
    error_messages: List[str]

def validate_roller_specs(state: ConveyorState):
    specs = state.get('specs', {})
    errors = []
    if specs.get('load_capacity_kg', 0) <= 0:
        errors.append('Load capacity must be positive.')
    return {'validation_passed': len(errors) == 0, 'error_messages': errors}

def update_procurement_status(state: ConveyorState):
    return {'status': 'Validated' if state['validation_passed'] else 'Rejected'}

graph = StateGraph(ConveyorState)
graph.add_node('validate', validate_roller_specs)
graph.add_node('status', update_procurement_status)
graph.add_edge('validate', 'status')
graph.add_edge('status', END)
graph.set_entry_point('validate')
graph = graph.compile()
