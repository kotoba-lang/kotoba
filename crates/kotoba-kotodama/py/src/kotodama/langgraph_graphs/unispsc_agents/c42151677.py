from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalKitState(TypedDict):
    kit_id: str
    compliance_checked: bool
    sterility_verified: bool

def validate_medical_compliance(state: DentalKitState):
    print(f'Checking compliance for {state.get('kit_id')}')
    return {'compliance_checked': True}

def verify_sterility(state: DentalKitState):
    print('Verifying sterile packaging integrity')
    return {'sterility_verified': True}

graph = StateGraph(DentalKitState)
graph.add_node('compliance', validate_medical_compliance)
graph.add_node('sterility', verify_sterility)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'sterility')
graph.add_edge('sterility', END)
graph = graph.compile()
