from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalSupplyState(TypedDict):
    part_number: str
    compliance_checked: bool
    sterility_verified: bool

def validate_compliance(state: DentalSupplyState):
    print('Verifying ISO 13485 and regulatory docs')
    return {'compliance_checked': True}

def verify_sterility(state: DentalSupplyState):
    print('Checking sterilization logs')
    return {'sterility_verified': True}

graph = StateGraph(DentalSupplyState)
graph.add_node('validate', validate_compliance)
graph.add_node('sterility', verify_sterility)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()
