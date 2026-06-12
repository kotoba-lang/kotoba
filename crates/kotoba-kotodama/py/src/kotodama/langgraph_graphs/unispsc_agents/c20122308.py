from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    robot_id: str
    spec_check_passed: bool
    safety_score: float
    processing_steps: Annotated[Sequence[str], operator.add]

def analyze_robot_specs(state: RobotState) -> RobotState:
    # Simulate fine-grained validation logic
    state['spec_check_passed'] = True
    return {'processing_steps': ['analyze_specs']}

def evaluate_safety(state: RobotState) -> RobotState:
    state['safety_score'] = 0.95
    return {'processing_steps': ['evaluate_safety']}

workflow = StateGraph(RobotState)
workflow.add_node('analyze', analyze_robot_specs)
workflow.add_node('safety', evaluate_safety)
workflow.set_entry_point('analyze')
workflow.add_edge('analyze', 'safety')
workflow.add_edge('safety', END)
graph = workflow.compile()
