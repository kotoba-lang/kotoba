from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BerylliumSpecState(TypedDict):
    material_compliance: bool
    clearance_check: bool
    dimensions: dict
    approved: bool

def validate_materials(state: BerylliumSpecState):
    state['material_compliance'] = True
    return state

def check_export_controls(state: BerylliumSpecState):
    state['clearance_check'] = True
    return state

def finalize_spec(state: BerylliumSpecState):
    state['approved'] = state['material_compliance'] and state['clearance_check']
    return state

graph = StateGraph(BerylliumSpecState)
graph.add_node('validate', validate_materials)
graph.add_node('export', check_export_controls)
graph.add_node('finalize', finalize_spec)
graph.add_edge('validate', 'export')
graph.add_edge('export', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
