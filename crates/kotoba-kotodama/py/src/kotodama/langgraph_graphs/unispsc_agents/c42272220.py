from typing import TypedDict
from langgraph.graph import StateGraph, END

class VentilatorState(TypedDict):
    part_number: str
    compliance_docs: list
    is_validated: bool

def validate_accessory(state: VentilatorState):
    # Simulate regulatory compliance checks for medical accessories
    state['is_validated'] = all(['certificate' in doc for doc in state.get('compliance_docs', [])])
    return state

def route_by_validation(state: VentilatorState):
    return 'valid' if state.get('is_validated') else 'flagged'

graph = StateGraph(VentilatorState)
graph.add_node('validate', validate_accessory)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
