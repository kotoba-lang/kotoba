from typing import TypedDict
from langgraph.graph import StateGraph, END

class GrenadeProcurementState(TypedDict):
    item_id: str
    compliance_cleared: bool
    shipping_safety_check: bool

def check_compliance(state: GrenadeProcurementState):
    state['compliance_cleared'] = True
    return state

def verify_safety(state: GrenadeProcurementState):
    state['shipping_safety_check'] = True
    return state

graph = StateGraph(GrenadeProcurementState)
graph.add_node('compliance', check_compliance)
graph.add_node('safety', verify_safety)
graph.add_edge('compliance', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('compliance')
graph = graph.compile()
