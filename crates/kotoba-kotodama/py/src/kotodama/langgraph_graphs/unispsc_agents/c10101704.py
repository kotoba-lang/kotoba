from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class WildlifeManagementState(TypedDict):
    area_id: str
    target_species: str
    capture_threshold: float
    logs: List[str]

def validate_area(state: WildlifeManagementState):
    return {"logs": state.get("logs", []) + ["Area validated for wildlife capture setup."]}

def deploy_traps(state: WildlifeManagementState):
    return {"logs": state.get("logs", []) + ["Automated trapping mechanism deployed."]}

def monitor_status(state: WildlifeManagementState):
    return {"logs": state.get("logs", []) + ["Real-time sensor monitoring active."]}

graph = StateGraph(WildlifeManagementState)
graph.add_node("validate", validate_area)
graph.add_node("deploy", deploy_traps)
graph.add_node("monitor", monitor_status)
graph.set_entry_point("validate")
graph.add_edge("validate", "deploy")
graph.add_edge("deploy", "monitor")
graph.add_edge("monitor", END)
graph = graph.compile()
