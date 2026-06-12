from langgraph.graph import StateGraph, END
from typing import TypedDict

class PinballState(TypedDict):
    serial_number: str
    compliance_checked: bool
    maintenance_plan: str

def validate_components(state: PinballState):
    state['compliance_checked'] = True
    return state

def finalize_order(state: PinballState):
    return state

graph = StateGraph(PinballState)
graph.add_node('validate', validate_components)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
