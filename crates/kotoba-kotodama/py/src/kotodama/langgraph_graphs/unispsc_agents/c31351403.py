from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    assembly_id: str
    material_certified: bool
    pressure_test_passed: bool

def validate_material(state: State) -> State:
    # Simulate material spec checking
    state['material_certified'] = True
    return state

def run_pressure_test(state: State) -> State:
    state['pressure_test_passed'] = True
    return state

graph = StateGraph(State)
graph.add_node('validate', validate_material)
graph.add_node('pressure_test', run_pressure_test)
graph.set_entry_point('validate')
graph.add_edge('validate', 'pressure_test')
graph.add_edge('pressure_test', END)
graph = graph.compile()
