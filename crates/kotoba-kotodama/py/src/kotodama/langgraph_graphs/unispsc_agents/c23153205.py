from typing import TypedDict
from langgraph.graph import StateGraph, END

class FastenerState(TypedDict):
    part_number: str
    material_certified: bool
    torque_verified: bool

def validate_material(state: FastenerState):
    state['material_certified'] = True
    return state

def check_torque(state: FastenerState):
    state['torque_verified'] = True
    return state

graph = StateGraph(FastenerState)
graph.add_node('material', validate_material)
graph.add_node('torque', check_torque)
graph.add_edge('material', 'torque')
graph.add_edge('torque', END)
graph.set_entry_point('material')
graph = graph.compile()
