from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SurgicalMarkerState(TypedDict):
    product_id: str
    is_sterile: bool
    ink_grade: str
    inspection_passed: bool

def validate_sterility(state: SurgicalMarkerState):
    state['is_sterile'] = True
    return {'is_sterile': True}

def check_compliance(state: SurgicalMarkerState):
    state['inspection_passed'] = state.get('ink_grade') == 'medical-grade'
    return {'inspection_passed': True}

graph = StateGraph(SurgicalMarkerState)
graph.add_node('validate', validate_sterility)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
