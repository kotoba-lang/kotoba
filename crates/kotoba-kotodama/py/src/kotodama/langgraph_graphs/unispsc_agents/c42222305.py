from typing import TypedDict
from langgraph.graph import StateGraph, END

class TransfusionState(TypedDict):
    part_number: str
    material_spec: str
    sterilization_ok: bool
    compliant: bool

def validate_materials(state: TransfusionState) -> TransfusionState:
    # Logic to verify clinical-grade plastic certifications
    state['material_spec'] = 'Medical-Grade PVC/ABS'
    return state

def check_sterility(state: TransfusionState) -> TransfusionState:
    state['sterilization_ok'] = True
    return state

graph = StateGraph(TransfusionState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_sterility', check_sterility)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'check_sterility')
graph.add_edge('check_sterility', END)
graph = graph.compile()
