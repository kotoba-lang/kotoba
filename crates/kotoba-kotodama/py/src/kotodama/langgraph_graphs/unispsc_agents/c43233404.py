from typing import TypedDict
from langgraph.graph import StateGraph, END

class SoftwareProcurementState(TypedDict):
    license_key: str
    compatibility_verified: bool
    media_integrity_check: bool

def validate_license(state: SoftwareProcurementState):
    state['license_key'] = 'VALIDATED'
    return state

def check_compatibility(state: SoftwareProcurementState):
    state['compatibility_verified'] = True
    return state

graph = StateGraph(SoftwareProcurementState)
graph.add_node('validate_license', validate_license)
graph.add_node('check_compatibility', check_compatibility)
graph.set_entry_point('validate_license')
graph.add_edge('validate_license', 'check_compatibility')
graph.add_edge('check_compatibility', END)
graph = graph.compile()
