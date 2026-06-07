from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    spec_data: dict
    validation_passed: bool
    errors: List[str]

def validate_dimensional_specs(state: CastingState):
    # Simulate CAD/Tolerance validation logic
    tolerance = state.get('spec_data', {}).get('tolerance', 0.05)
    passed = tolerance <= 0.1
    return {'validation_passed': passed, 'errors': [] if passed else ['Tolerance out of limit']}

def perform_ndt_check(state: CastingState):
    # Simulate Non-Destructive Testing routing
    print('Running ultrasonic inspection on shell mold casting...')
    return {'validation_passed': True}

graph = StateGraph(CastingState)
graph.add_node('validate', validate_dimensional_specs)
graph.add_node('ndt_check', perform_ndt_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'ndt_check')
graph.add_edge('ndt_check', END)
graph = graph.compile()
