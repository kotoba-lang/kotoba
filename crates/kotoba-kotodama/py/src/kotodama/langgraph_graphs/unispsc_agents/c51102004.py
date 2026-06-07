from typing import TypedDict
from langgraph.graph import StateGraph, END

class RifabutinState(TypedDict):
    purity_validated: bool
    gmp_compliant: bool
    storage_temp_verified: bool

def validate_quality(state: RifabutinState):
    state['purity_validated'] = True
    return state

def check_compliance(state: RifabutinState):
    state['gmp_compliant'] = True
    return state

graph = StateGraph(RifabutinState)
graph.add_node('validate', validate_quality)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)

graph = graph.compile()
