from typing import TypedDict
from langgraph.graph import StateGraph, END

class MedicalSupplyState(TypedDict):
    product_id: str
    is_sterile: bool
    regulatory_compliant: bool
    approved: bool

def validate_compliance(state: MedicalSupplyState):
    state['regulatory_compliant'] = True
    return state

def check_sterility(state: MedicalSupplyState):
    state['is_sterile'] = True
    state['approved'] = state['is_sterile'] and state['regulatory_compliant']
    return state

graph = StateGraph(MedicalSupplyState)
graph.add_node('validate_compliance', validate_compliance)
graph.add_node('check_sterility', check_sterility)
graph.set_entry_point('validate_compliance')
graph.add_edge('validate_compliance', 'check_sterility')
graph.add_edge('check_sterility', END)
graph = graph.compile()
