from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotControlState(TypedDict):
    axis_commands: List[dict]
    status: str
    validation_errors: List[str]

def validate_kinematics(state: RobotControlState) -> RobotControlState:
    # Logic for validating movement kinematics
    state['status'] = 'kinematics_validated'
    return state

def execute_motion(state: RobotControlState) -> RobotControlState:
    # Logic for processing motor control packets
    state['status'] = 'motion_executed'
    return state

def graph_builder():
    graph = StateGraph(RobotControlState)
    graph.add_node('validate', validate_kinematics)
    graph.add_node('execute', execute_motion)
    graph.set_entry_point('validate')
    graph.add_edge('validate', 'execute')
    graph.add_edge('execute', END)
    return graph.compile()

graph = graph_builder()
