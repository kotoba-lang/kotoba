from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    item_name: str
    sterile_checked: bool
    compliance_verified: bool

def validate_sterile(state: DentalSupplyState):
    state['sterile_checked'] = True
    return state

def check_compliance(state: DentalSupplyState):
    state['compliance_verified'] = True
    return state

graph = StateGraph(DentalSupplyState)
graph.add_node('validate_sterile', validate_sterile)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_sterile')
graph.add_edge('validate_sterile', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()
