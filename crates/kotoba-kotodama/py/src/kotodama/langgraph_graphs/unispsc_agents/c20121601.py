from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class EquipmentProcurementState(TypedDict):
    commodity_code: str
    validation_checks: List[str]
    approved: bool

def validate_specs(state: EquipmentProcurementState):
    # Simulate spec validation logic
    return {'validation_checks': ['ISO_cert_verified', 'maintenance_terms_ok'], 'approved': True}

def approve_workflow(state: EquipmentProcurementState):
    return {'approved': True}

graph = StateGraph(EquipmentProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approve_workflow)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
