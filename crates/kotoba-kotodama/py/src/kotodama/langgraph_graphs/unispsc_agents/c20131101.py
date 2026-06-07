from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GearState(TypedDict):
    part_number: str
    material_compliance: bool
    torque_check: bool
    approved: bool

def validate_material(state: GearState) -> GearState:
    state['material_compliance'] = True
    return state

def check_torque(state: GearState) -> GearState:
    state['torque_check'] = True
    return state

def finalize_check(state: GearState) -> GearState:
    state['approved'] = state['material_compliance'] and state['torque_check']
    return state

graph = StateGraph(GearState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_torque', check_torque)
graph.add_node('finalize', finalize_check)
graph.add_edge('validate_material', 'check_torque')
graph.add_edge('check_torque', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate_material')
graph = graph.compile()
