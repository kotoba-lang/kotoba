from typing import TypedDict
from langgraph.graph import StateGraph, END

class MedEquipState(TypedDict):
    equipment_id: str
    regulatory_compliant: bool
    sterility_check: bool
    final_approval: bool

def validate_compliance(state: MedEquipState):
    # Simulate regulatory API check
    return {'regulatory_compliant': True}

def verify_sterility(state: MedEquipState):
    # Simulate sterility documentation verification
    return {'sterility_check': True}

graph = StateGraph(MedEquipState)
graph.add_node('verify_regulatory', validate_compliance)
graph.add_node('verify_sterility', verify_sterility)
graph.set_entry_point('verify_regulatory')
graph.add_edge('verify_regulatory', 'verify_sterility')
graph.add_edge('verify_sterility', END)
graph = graph.compile()
