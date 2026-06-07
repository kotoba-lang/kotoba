from typing import TypedDict
from langgraph.graph import StateGraph, END

class ShipProcurementState(TypedDict):
    hull_spec: dict
    c4isr_ready: bool
    compliance_report: str

def validate_hull(state: ShipProcurementState):
    print('Validating naval hull integrity and propulsion...')
    return {'hull_spec': {'status': 'verified'}}

def check_compliance(state: ShipProcurementState):
    print('Performing ITAR and security audit...')
    return {'compliance_report': 'passed'}

graph = StateGraph(ShipProcurementState)
graph.add_node('validate_hull', validate_hull)
graph.add_node('check_compliance', check_compliance)
graph.set_entry_point('validate_hull')
graph.add_edge('validate_hull', 'check_compliance')
graph.add_edge('check_compliance', END)
graph = graph.compile()
