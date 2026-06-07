from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BarracksState(TypedDict):
    site_location: str
    unit_capacity: int
    safety_certs: List[str]
    approved: bool

def validate_engineering(state: BarracksState):
    return {"approved": len(state.get("safety_certs", [])) > 0}

def deploy_procurement(state: BarracksState):
    return {"approved": True}

graph = StateGraph(BarracksState)
graph.add_node("validate", validate_engineering)
graph.add_node("deploy", deploy_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "deploy")
graph.add_edge("deploy", END)
graph = graph.compile()
