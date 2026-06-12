from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class RobotControllerState(TypedDict):
    controller_id: str
    validation_passed: bool
    task_steps: Annotated[list[str], operator.add]

def validate_controller(state: RobotControllerState) -> dict:
    passed = state.get('controller_id', '').startswith('RC-')
    return {'validation_passed': passed}

def prepare_workflow(state: RobotControllerState) -> dict:
    return {'task_steps': ['Initialize Safety Protocols', 'Configure Axis Mapping', 'Establish PLC Handshake']}

def deploy_controller(state: RobotControllerState) -> dict:
    return {'task_steps': ['Execute Calibration Sequence']}

graph = StateGraph(RobotControllerState)
graph.add_node('validate', validate_controller)
graph.add_node('prepare', prepare_workflow)
graph.add_node('deploy', deploy_controller)
graph.set_entry_point('validate')
graph.add_edge('validate', 'prepare')
graph.add_edge('prepare', 'deploy')
graph.add_edge('deploy', END)
graph = graph.compile()
