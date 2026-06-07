from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    part_id: str
    safety_verified: bool
    precision_validated: bool
    status: str

def check_safety(state: RobotState):
    return {"safety_verified": True, "status": "safety_checked"}

def validate_precision(state: RobotState):
    return {"precision_validated": True, "status": "precision_validated"}

graph = StateGraph(RobotState)
graph.add_node("check_safety", check_safety)
graph.add_node("validate_precision", validate_precision)
graph.add_edge("check_safety", "validate_precision")
graph.add_edge("validate_precision", END)
graph.set_entry_point("check_safety")
graph = graph.compile()
