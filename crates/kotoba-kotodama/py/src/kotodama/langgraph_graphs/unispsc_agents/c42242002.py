from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProstheticState(TypedDict):
    device_id: str
    compliance_checked: bool
    fit_validation: bool

def validate_medical_standards(state: ProstheticState):
    state['compliance_checked'] = True
    return state

def validate_biomechanical_fit(state: ProstheticState):
    state['fit_validation'] = True
    return state

graph = StateGraph(ProstheticState)
graph.add_node('compliance', validate_medical_standards)
graph.add_node('fit', validate_biomechanical_fit)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'fit')
graph.add_edge('fit', END)
graph = graph.compile()
