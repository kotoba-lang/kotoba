from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DrugState(TypedDict):
    lot_number: str
    cold_chain_status: bool
    compliance_checked: bool

def validate_cold_chain(state: DrugState):
    state['cold_chain_status'] = True
    return state

def check_compliance(state: DrugState):
    state['compliance_checked'] = True
    return state

graph = StateGraph(DrugState)
graph.add_node('validate', validate_cold_chain)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
