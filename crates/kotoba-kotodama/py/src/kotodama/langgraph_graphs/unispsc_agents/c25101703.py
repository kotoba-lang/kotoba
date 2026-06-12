from typing import TypedDict
from langgraph.graph import StateGraph, END

class AmbulanceProcurementState(TypedDict):
    vehicle_specs: dict
    compliance_checks: list
    approval_status: bool

def validate_specs(state: AmbulanceProcurementState):
    # Perform logic to check if medical equipment fits specs
    return {'compliance_checks': ['ISO_EN1789_Certified']}

def check_regulations(state: AmbulanceProcurementState):
    return {'approval_status': True}

graph = StateGraph(AmbulanceProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_regulations)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
