from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotControlState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_report: str

def validate_specs(state: RobotControlState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['payload', 'precision'])
    print(f'Validating: {specs}')
    return {'validation_passed': is_valid}

def generate_compliance(state: RobotControlState):
    return {'compliance_report': 'ISO-10218-1 Certified' if state['validation_passed'] else 'Manual Review Required'}

graph = StateGraph(RobotControlState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', generate_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
