from typing import TypedDict
from langgraph.graph import StateGraph, END

class VehicleProcurementState(TypedDict):
    vehicle_id: str
    compliance_cleared: bool
    inspection_report: str

def validate_vehicle_specs(state: VehicleProcurementState):
    # Simulate CAD and safety validation
    state['compliance_cleared'] = True
    return state

def approve_procurement(state: VehicleProcurementState):
    state['inspection_report'] = 'Validation Completed'
    return state

graph = StateGraph(VehicleProcurementState)
graph.add_node('validate', validate_vehicle_specs)
graph.add_node('approve', approve_procurement)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
