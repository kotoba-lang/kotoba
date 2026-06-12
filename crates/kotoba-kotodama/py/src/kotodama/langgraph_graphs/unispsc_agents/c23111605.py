from typing import TypedDict
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    model_id: str
    payload_check: bool
    safety_compliance: bool

def validate_payload(state: RobotState):
    return {"payload_check": state.get("payload_id", 0) > 0}

def validate_safety(state: RobotState):
    return {"safety_compliance": True}

workflow = StateGraph(RobotState)
workflow.add_node("validate_payload", validate_payload)
workflow.add_node("validate_safety", validate_safety)
workflow.add_edge("validate_payload", "validate_safety")
workflow.add_edge("validate_safety", END)
workflow.set_entry_point("validate_payload")
graph = workflow.compile()
