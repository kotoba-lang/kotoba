from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OxygenSupplyState(TypedDict):
    part_number: str
    material_certified: bool
    sterility_valid: bool
    is_approved: bool

def validate_materials(state: OxygenSupplyState):
    # Simulate material compliance check for medical tubing
    state['material_certified'] = True
    return state

def check_sterility(state: OxygenSupplyState):
    # Simulate sterility compliance verification
    state['sterility_valid'] = True
    state['is_approved'] = state['material_certified'] and state['sterility_valid']
    return state

graph = StateGraph(OxygenSupplyState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_sterility', check_sterility)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'check_sterility')
graph.add_edge('check_sterility', END)

graph = graph.compile()
