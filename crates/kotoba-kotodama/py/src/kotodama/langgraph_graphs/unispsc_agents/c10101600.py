from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    livestock_id: str
    health_status: str
    quarantine_clearance: bool
    history: List[str]

def validate_health_records(state: LivestockState):
    if state.get("health_status") == "certified":
        return {"history": state["history"] + ["Health check passed"]}
    raise ValueError("Health certification required")

def check_quarantine(state: LivestockState):
    if state.get("quarantine_clearance"):
        return {"history": state["history"] + ["Quarantine cleared"]}
    return {"history": state["history"] + ["Quarantine pending"]}

graph = StateGraph(LivestockState)
graph.add_node("validate_health", validate_health_records)
graph.add_node("check_quarantine", check_quarantine)
graph.add_edge("validate_health", "check_quarantine")
graph.add_edge("check_quarantine", END)
graph.set_entry_point("validate_health")
graph = graph.compile()
