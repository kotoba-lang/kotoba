from typing import TypedDict
from langgraph.graph import StateGraph, END

class VitrectomyState(TypedDict):
    serial_number: str
    sterility_certificate: bool
    optical_clearance: bool
    approved: bool

def validate_sterility(state: VitrectomyState):
    return {"sterility_certificate": state.get("sterility_certificate", False)}

def validate_optics(state: VitrectomyState):
    return {"optical_clearance": True}

def final_check(state: VitrectomyState):
    is_approved = state["sterility_certificate"] and state["optical_clearance"]
    return {"approved": is_approved}

graph = StateGraph(VitrectomyState)
graph.add_node("sterility", validate_sterility)
graph.add_node("optics", validate_optics)
graph.add_node("approval", final_check)

graph.set_entry_point("sterility")
graph.add_edge("sterility", "optics")
graph.add_edge("optics", "approval")
graph.add_edge("approval", END)

graph = graph.compile()
