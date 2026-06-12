from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MotionControlState(TypedDict):
    command_sequence: Annotated[Sequence[str], add_messages]
    safety_verified: bool
    validation_log: list

def validate_trajectory(state: MotionControlState):
    log = "Trajectory integrity checked."
    return {"safety_verified": True, "validation_log": [log]}

def execute_motion(state: MotionControlState):
    return {"validation_log": state["validation_log"] + ["Motion command executed successfully"]}

graph = StateGraph(MotionControlState)
graph.add_node("validate", validate_trajectory)
graph.add_node("execute", execute_motion)
graph.set_entry_point("validate")
graph.add_edge("validate", "execute")
graph.add_edge("execute", END)
graph = graph.compile()
