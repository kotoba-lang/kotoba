from typing import TypedDict, Annotated
import operator
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    task_id: str
    path_plan: list
    validation_log: Annotated[list, operator.add]
    is_safe: bool

def plan_motion(state: RobotState) -> RobotState:
    return {"path_plan": ["move_to_home", "calibrate", "execute_path"]}

def validate_safety(state: RobotState) -> RobotState:
    return {"is_safe": True, "validation_log": ["Safety check passed for payload"]}

def finalize_execution(state: RobotState) -> RobotState:
    return {"validation_log": ["Execution complete"]}

workflow = StateGraph(RobotState)
workflow.add_node("planner", plan_motion)
workflow.add_node("safety", validate_safety)
workflow.add_node("executor", finalize_execution)

workflow.set_entry_point("planner")
workflow.add_edge("planner", "safety")
workflow.add_edge("safety", "executor")
workflow.add_edge("executor", END)

graph = workflow.compile()
