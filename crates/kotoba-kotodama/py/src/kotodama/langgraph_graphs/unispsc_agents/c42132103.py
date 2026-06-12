from typing import TypedDict
from langgraph.graph import StateGraph, END

class BarrierDrapeState(TypedDict):
    drape_id: str
    is_sterile: bool
    compliance_verified: bool

def validate_sterility(state: BarrierDrapeState):
    state['is_sterile'] = True
    return state

def verify_compliance(state: BarrierDrapeState):
    state['compliance_verified'] = True
    return state

graph = StateGraph(BarrierDrapeState)
graph.add_node('validate_sterility', validate_sterility)
graph.add_node('verify_compliance', verify_compliance)
graph.set_entry_point('validate_sterility')
graph.add_edge('validate_sterility', 'verify_compliance')
graph.add_edge('verify_compliance', END)
graph = graph.compile()
