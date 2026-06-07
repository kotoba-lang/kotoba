from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    spec_data: dict
    validated: bool
    compliance_report: str

def validate_robot_specs(state: RobotState):
    specs = state.get('spec_data', {})
    is_valid = all(k in specs for k in ['payload', 'reach'])
    return {'validated': is_valid, 'compliance_report': 'Passed' if is_valid else 'Missing mandatory specs'}

def route_by_compliance(state: RobotState):
    return 'process' if state['validated'] else END

graph = StateGraph(RobotState)
graph.add_node('validate', validate_robot_specs)
graph.add_node('process', lambda x: {'compliance_report': 'Deployment sequence initiated'})
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance)
graph.add_edge('process', END)
graph = graph.compile()
