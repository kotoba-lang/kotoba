from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalState(TypedDict):
    product_id: str
    is_sterile: bool
    compliance_validated: bool

def validate_sterility(state: SurgicalState):
    return {'compliance_validated': state.get('is_sterile', False)}

def check_compliance(state: SurgicalState):
    return {'compliance_validated': True}

graph = StateGraph(SurgicalState)
graph.add_node('validate', validate_sterility)
graph.add_node('check', check_compliance)
graph.add_edge('validate', 'check')
graph.add_edge('check', END)
graph.set_entry_point('validate')
graph = graph.compile()
