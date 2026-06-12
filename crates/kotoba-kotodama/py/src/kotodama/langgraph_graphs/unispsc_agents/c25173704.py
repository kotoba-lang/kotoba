from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    part_specs: dict
    validation_passed: bool

def validate_dimensions(state: State) -> State:
    specs = state.get('part_specs', {})
    required = ['id', 'od', 'material']
    state['validation_passed'] = all(k in specs for k in required)
    return state

def check_thermal_tolerance(state: State) -> str:
    return 'pass' if state['validation_passed'] else 'fail'

graph = StateGraph(State)
graph.add_node('validate', validate_dimensions)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
