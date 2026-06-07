from typing import TypedDict
from langgraph.graph import StateGraph, END

class SupplyState(TypedDict):
    item_code: str
    is_sterile: bool
    compliance_checked: bool

def check_sterility(state: SupplyState):
    state['is_sterile'] = True
    return state

def validate_compliance(state: SupplyState):
    state['compliance_checked'] = True
    return state

graph = StateGraph(SupplyState)
graph.add_node('check_sterility', check_sterility)
graph.add_node('validate_compliance', validate_compliance)
graph.set_entry_point('check_sterility')
graph.add_edge('check_sterility', 'validate_compliance')
graph.add_edge('validate_compliance', END)
graph = graph.compile()
