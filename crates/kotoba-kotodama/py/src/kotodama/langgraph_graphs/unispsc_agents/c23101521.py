from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class RobotProcurementState(TypedDict):
    specifications: dict
    validation_status: str
    compliance_risk: List[str]

def validate_robot_specs(state: RobotProcurementState):
    specs = state.get('specifications', {})
    if specs.get('payload_capacity_kg', 0) > 0 and 'iso10218' in str(specs.get('certifications', '')):
        return {'validation_status': 'verified'}
    return {'validation_status': 'requires_review'}

def check_compliance(state: RobotProcurementState):
    return {'compliance_risk': ['export_control_check']}

graph = StateGraph(RobotProcurementState)
graph.add_node('validate', validate_robot_specs)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
