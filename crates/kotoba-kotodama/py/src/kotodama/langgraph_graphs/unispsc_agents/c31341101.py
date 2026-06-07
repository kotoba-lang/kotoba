from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    assembly_id: str
    material_certified: bool
    weld_inspection_passed: bool
    status: str

def validate_material(state: AssemblyState) -> AssemblyState:
    # Logic to verify aluminum alloy certification
    state['material_certified'] = True
    return state

def check_welds(state: AssemblyState) -> AssemblyState:
    # Logic to confirm NDT results for brazing/welding integrity
    state['weld_inspection_passed'] = True
    return state

def finalize_order(state: AssemblyState) -> AssemblyState:
    state['status'] = 'READY_FOR_SHIPMENT' if state['material_certified'] and state['weld_inspection_passed'] else 'REJECTED'
    return state

graph = StateGraph(AssemblyState)
graph.add_node('validate', validate_material)
graph.add_node('check', check_welds)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'check')
graph.add_edge('check', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
