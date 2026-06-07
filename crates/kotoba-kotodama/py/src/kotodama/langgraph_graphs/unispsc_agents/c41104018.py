from typing import TypedDict
from langgraph.graph import StateGraph, END

class SPEState(TypedDict):
    purity_validated: bool
    compliance_checked: bool

def validate_specs(state: SPEState):
    state['purity_validated'] = True
    return state

def check_compliance(state: SPEState):
    state['compliance_checked'] = True
    return state

graph = StateGraph(SPEState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
