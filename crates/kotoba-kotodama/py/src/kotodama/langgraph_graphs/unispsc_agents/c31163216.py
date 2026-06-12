from typing import TypedDict
from langgraph.graph import StateGraph, END

class CableHangerState(TypedDict):
    material: str
    load_capacity: float
    inspection_passed: bool

def validate_material(state: CableHangerState):
    print(f'Validating material: {state.get('material')}')
    return {'inspection_passed': True}

def check_load(state: CableHangerState):
    capacity = state.get('load_capacity', 0)
    status = capacity > 0
    return {'inspection_passed': status}

graph = StateGraph(CableHangerState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_load', check_load)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_load')
graph.add_edge('check_load', END)
graph = graph.compile()
