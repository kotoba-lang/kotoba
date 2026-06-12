from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class RobotState(TypedDict):
    part_id: str
    spec_requirements: dict
    validation_log: Annotated[List[str], operator.add]
    is_compliant: bool

def validate_gripper_specs(state: RobotState):
    specs = state.get('spec_requirements', {})
    if specs.get('payload_capacity_kg', 0) > 0:
        return {'validation_log': ['Payload capacity verified'], 'is_compliant': True}
    return {'validation_log': ['Payload capacity missing'], 'is_compliant': False}

def assembly_workflow(state: RobotState):
    return {'validation_log': ['Workflow initialized for end-effector integration']}

graph = StateGraph(RobotState)
graph.add_node('validate', validate_gripper_specs)
graph.add_node('workflow', assembly_workflow)
graph.add_edge('validate', 'workflow')
graph.add_edge('workflow', END)
graph.set_entry_point('validate')
graph = graph.compile()
