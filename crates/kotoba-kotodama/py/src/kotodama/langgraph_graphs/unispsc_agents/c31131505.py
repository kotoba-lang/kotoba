from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    material_certified: bool
    ultrasonic_passed: bool
    dimensions_verified: bool
    status: str

def validate_material(state: ForgingState):
    print('Validating material properties...')
    return {'material_certified': True}

def perform_ultrasonic_test(state: ForgingState):
    print('Executing ultrasonic inspection...')
    return {'ultrasonic_passed': True}

graph = StateGraph(ForgingState)
graph.add_node('material', validate_material)
graph.add_node('ultrasonic', perform_ultrasonic_test)
graph.set_entry_point('material')
graph.add_edge('material', 'ultrasonic')
graph.add_edge('ultrasonic', END)
graph = graph.compile()
