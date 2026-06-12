from typing import TypedDict
from langgraph.graph import StateGraph, END

class DentalExpandersState(TypedDict):
    material_compliance: bool
    sterilization_verified: bool
    regulatory_approved: bool

def check_compliance(state: DentalExpandersState):
    return {'material_compliance': True, 'regulatory_approved': True}

def verify_sterilization(state: DentalExpandersState):
    return {'sterilization_verified': True}

graph = StateGraph(DentalExpandersState)
graph.add_node('compliance', check_compliance)
graph.add_node('sterilization', verify_sterilization)
graph.add_edge('compliance', 'sterilization')
graph.add_edge('sterilization', END)
graph.set_entry_point('compliance')
graph = graph.compile()
