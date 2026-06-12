from typing import TypedDict
from langgraph.graph import StateGraph, END

class BuprenorphineState(TypedDict):
    license_validated: bool
    quantity_within_limit: bool
    storage_confirmed: bool

def validate_license(state: BuprenorphineState):
    state['license_validated'] = True
    return state

def check_compliance(state: BuprenorphineState):
    state['quantity_within_limit'] = True
    return state

graph = StateGraph(BuprenorphineState)
graph.add_node('validate', validate_license)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
