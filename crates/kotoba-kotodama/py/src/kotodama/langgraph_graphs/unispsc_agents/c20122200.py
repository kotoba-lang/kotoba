from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotProcurementState(TypedDict):
    commodity_code: str
    specifications: dict
    validation_checks: List[str]
    approved: bool

def validate_safety_standards(state: RobotProcurementState) -> RobotProcurementState:
    spec = state.get('specifications', {})
    if spec.get('safety_certification_iso10218'):
        state['validation_checks'].append('ISO-10218 Validated')
    return state

def assess_operational_risks(state: RobotProcurementState) -> RobotProcurementState:
    payload = state.get('specifications', {}).get('payload_capacity_kg', 0)
    if payload > 500:
        state['validation_checks'].append('High-Payload-Risk-Flag')
    return state

graph = StateGraph(RobotProcurementState)
graph.add_node('safety_check', validate_safety_standards)
graph.add_node('risk_assessment', assess_operational_risks)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'risk_assessment')
graph.add_edge('risk_assessment', END)
graph = graph.compile()
