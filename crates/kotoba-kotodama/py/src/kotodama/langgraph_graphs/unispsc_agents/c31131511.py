from typing import TypedDict
from langgraph.graph import StateGraph, END

class ForgingState(TypedDict):
    material_grade: str
    is_compliant: bool
    inspection_passed: bool

def validate_specs(state: ForgingState):
    state['is_compliant'] = state.get('material_grade') in ['C3604', 'C3771']
    return state

def check_quality(state: ForgingState):
    state['inspection_passed'] = True if state['is_compliant'] else False
    return state

graph = StateGraph(ForgingState)
graph.add_node('validate', validate_specs)
graph.add_node('inspection', check_quality)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspection')
graph.add_edge('inspection', END)
graph = graph.compile()
