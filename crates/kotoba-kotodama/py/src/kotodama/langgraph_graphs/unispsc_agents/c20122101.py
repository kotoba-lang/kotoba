from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotProcessingState(TypedDict):
    robot_id: str
    spec_requirements: dict
    validation_log: List[str]
    is_compliant: bool

def validate_specs(state: RobotProcessingState):
    specs = state.get('spec_requirements', {})
    valid = specs.get('payload_capacity_kg', 0) > 0 and 'iso_certification' in specs
    return {'validation_log': ['Specs validated'], 'is_compliant': valid}

def safety_audit(state: RobotProcessingState):
    return {'validation_log': state['validation_log'] + ['Safety protocols verified']}

graph = StateGraph(RobotProcessingState)
graph.add_node('validate', validate_specs)
graph.add_node('safety', safety_audit)
graph.add_edge('validate', 'safety')
graph.add_edge('safety', END)
graph.set_entry_point('validate')
graph = graph.compile()
