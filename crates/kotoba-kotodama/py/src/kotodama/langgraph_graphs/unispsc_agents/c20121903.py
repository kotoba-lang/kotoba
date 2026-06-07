from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotState(TypedDict):
    commodity_code: str
    specifications: dict
    validation_logs: List[str]
    status: str

def validate_robot_spec(state: RobotState):
    # Simulate CAD/Spec validation logic
    specs = state.get("specifications", {})
    if specs.get("degrees_of_freedom", 0) < 6:
        return {"validation_logs": ["Spec Validation Failed: Insufficient DOF"], "status": "REJECTED"}
    return {"validation_logs": ["Spec Validation Passed: Standard Industrial Grade"], "status": "READY"}

def deploy_robot_config(state: RobotState):
    # Simulate deployment preparation
    return {"validation_logs": state.get("validation_logs", []) + ["Deployment Configured"], "status": "DEPLOYED"}

graph = StateGraph(RobotState)
graph.add_node("validate", validate_robot_spec)
graph.add_node("deploy", deploy_robot_config)
graph.set_entry_point("validate")
graph.add_conditional_edges(
    "validate",
    lambda s: "deploy" if s["status"] == "READY" else END,
    {"deploy": "deploy", END: END}
)
graph.add_edge("deploy", END)
graph = graph.compile()
