from typing import TypedDict
from langgraph.graph import StateGraph, END

class ScalpelState(TypedDict):
    material_compliance: bool
    sterility_check: bool
    inspection_status: str

def validate_materials(state: ScalpelState) -> ScalpelState:
    state['material_compliance'] = True
    return state

def check_sterility(state: ScalpelState) -> ScalpelState:
    state['sterility_check'] = True
    return state

def finalize_inspection(state: ScalpelState) -> ScalpelState:
    state['inspection_status'] = 'PASSED' if state['material_compliance'] and state['sterility_check'] else 'FAILED'
    return state

graph = StateGraph(ScalpelState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('check_sterility', check_sterility)
graph.add_node('finalize', finalize_inspection)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'check_sterility')
graph.add_edge('check_sterility', 'finalize')
graph.add_edge('finalize', END)

graph = graph.compile()
