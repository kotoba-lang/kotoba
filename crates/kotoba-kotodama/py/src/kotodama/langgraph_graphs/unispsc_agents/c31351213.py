from typing import TypedDict
from langgraph.graph import StateGraph, END

class TubeAssemblyState(TypedDict):
    material_certified: bool
    pressure_test_passed: bool
    inspection_passed: bool

def validate_material(state: TubeAssemblyState):
    state['material_certified'] = True
    return state

def check_pressure(state: TubeAssemblyState):
    state['pressure_test_passed'] = True
    return state

def final_qa(state: TubeAssemblyState):
    state['inspection_passed'] = True
    return state

graph = StateGraph(TubeAssemblyState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_pressure', check_pressure)
graph.add_node('final_qa', final_qa)
graph.set_entry_point('validate_material')
graph.add_edge('validate_material', 'check_pressure')
graph.add_edge('check_pressure', 'final_qa')
graph.add_edge('final_qa', END)
graph = graph.compile()
