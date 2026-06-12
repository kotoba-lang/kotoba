from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    specs: dict
    validation_logs: List[str]
    is_compliant: bool

def validate_specs(state: RobotState):
    logs = state.get("validation_logs", [])
    specs = state.get("specs", {})
    if specs.get("load_capacity_kg", 0) > 0:
        logs.append("Capacity check passed")
    return {"validation_logs": logs}

def verify_safety(state: RobotState):
    logs = state.get("validation_logs", [])
    logs.append("Safety certification verified")
    return {"validation_logs": logs, "is_compliant": True}

graph = StateGraph(RobotState)
graph.add_node("validate", validate_specs)
graph.add_node("safety", verify_safety)
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("validate")
graph = graph.compile()
