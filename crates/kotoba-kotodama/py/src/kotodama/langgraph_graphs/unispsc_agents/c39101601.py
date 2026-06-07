from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LampState(TypedDict):
    specs: dict
    validation_errors: List[str]
    is_approved: bool

def validate_lamp_specs(state: LampState) -> LampState:
    specs = state.get('specs', {})
    errors = []
    if specs.get('wattage', 0) <= 0:
        errors.append('Invalid wattage')
    if not specs.get('base_type'):
        errors.append('Base type is required')
    return {**state, 'validation_errors': errors, 'is_approved': len(errors) == 0}

graph = StateGraph(LampState)
graph.add_node('validate', validate_lamp_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
