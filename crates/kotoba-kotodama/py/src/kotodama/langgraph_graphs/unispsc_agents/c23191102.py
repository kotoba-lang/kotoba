from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    spec_data: dict
    validation_results: dict

def validate_specs(state: RobotState):
    specs = state.get('spec_data', {})
    is_safe = specs.get('payload_capacity_kg', 0) > 0 and 'iso_10218' in specs.get('certs', [])
    return {'validation_results': {'is_valid': is_safe}}

def check_export_control(state: RobotState):
    return {'validation_results': {**state['validation_results'], 'export_clearance': True}}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_export_control)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
