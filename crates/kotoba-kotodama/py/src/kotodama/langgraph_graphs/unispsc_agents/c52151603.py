from typing import TypedDict
from langgraph.graph import StateGraph, END

class GraterSpecState(TypedDict):
    material: str
    compliance_cert: bool
    is_approved: bool

def validate_material(state: GraterSpecState):
    state['is_approved'] = state.get('material') == 'SUS304'
    return state

def check_compliance(state: GraterSpecState):
    if state.get('is_approved'):
        state['is_approved'] = state.get('compliance_cert', False)
    return state

graph = StateGraph(GraterSpecState)
graph.add_node('validate_material', validate_material)
graph.add_node('check_compliance', check_compliance)
graph.add_edge('validate_material', 'check_compliance')
graph.add_edge('check_compliance', END)
graph.set_entry_point('validate_material')
graph = graph.compile()
