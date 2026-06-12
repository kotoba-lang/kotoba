from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SurgicalTapState(TypedDict):
    material_grade: str
    sterility_verified: bool
    tolerance_check: bool

def validate_specs(state: SurgicalTapState):
    state['tolerance_check'] = True if state.get('material_grade') == 'Medical-Grade Stainless Steel' else False
    return state

def check_certification(state: SurgicalTapState):
    state['sterility_verified'] = True
    return state

graph = StateGraph(SurgicalTapState)
graph.add_node('validate', validate_specs)
graph.add_node('certify', check_certification)
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph.set_entry_point('validate')
graph = graph.compile()
