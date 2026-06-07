from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExcavatorState(TypedDict):
    spec_data: dict
    validation_passed: bool
    engine_check: str

def validate_specs(state: ExcavatorState):
    specs = state.get('spec_data', {})
    is_valid = 'Load Capacity' in specs and 'Safety Compliance' in specs
    return {'validation_passed': is_valid}

def check_emissions(state: ExcavatorState):
    return {'engine_check': 'Tier 4 Final Compliant'}

graph = StateGraph(ExcavatorState)
graph.add_node('validate', validate_specs)
graph.add_node('emissions', check_emissions)
graph.add_edge('validate', 'emissions')
graph.add_edge('emissions', END)
graph.set_entry_point('validate')
graph = graph.compile()
