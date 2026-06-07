from typing import TypedDict
from langgraph.graph import StateGraph, END

class AutomotiveState(TypedDict):
    part_specs: dict
    validation_status: bool
    compliance_report: str

def validate_specs(state: AutomotiveState):
    specs = state.get('part_specs', {})
    status = all(key in specs for key in ['torque_rating', 'material_grade', 'iso_cert'])
    return {'validation_status': status}

def generate_report(state: AutomotiveState):
    return {'compliance_report': 'Technical validation complete' if state['validation_status'] else 'Validation pending'}

graph = StateGraph(AutomotiveState)
graph.add_node('validate', validate_specs)
graph.add_node('report', generate_report)
graph.set_entry_point('validate')
graph.add_edge('validate', 'report')
graph.add_edge('report', END)
graph = graph.compile()
