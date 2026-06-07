from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: RobotState):
    specs = state.get('spec_data', {})
    valid = specs.get('load_capacity_kg', 0) > 0 and 'iso_certification_standard' in specs
    return {'validated': valid, 'error_log': [] if valid else ['Missing mandatory specs']}

def approval_step(state: RobotState):
    return {'validated': True}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_specs)
graph.add_node('approve', approval_step)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
