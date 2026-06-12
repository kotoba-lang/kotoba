from typing import TypedDict
from langgraph.graph import StateGraph, END

class RudderProcurementState(TypedDict):
    part_number: str
    certification_valid: bool
    inspection_passed: bool

def validate_part(state: RudderProcurementState):
    state['certification_valid'] = state.get('part_number', '').startswith('RUD')
    return state

def perform_inspection(state: RudderProcurementState):
    state['inspection_passed'] = state.get('certification_valid', False)
    return state

graph = StateGraph(RudderProcurementState)
graph.add_node('validate', validate_part)
graph.add_node('inspect', perform_inspection)
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph.set_entry_point('validate')
graph = graph.compile()
