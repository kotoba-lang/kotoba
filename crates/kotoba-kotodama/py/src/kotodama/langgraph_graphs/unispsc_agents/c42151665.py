from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalState(TypedDict):
    part_number: str
    tolerance_check: bool
    is_medical_certified: bool

def validate_compliance(state: DentalState):
    state['is_medical_certified'] = True
    return state

def check_precision(state: DentalState):
    state['tolerance_check'] = True
    return state

graph = StateGraph(DentalState)
graph.add_node('validate', validate_compliance)
graph.add_node('precision', check_precision)
graph.add_edge('validate', 'precision')
graph.add_edge('precision', END)
graph.set_entry_point('validate')
graph = graph.compile()
