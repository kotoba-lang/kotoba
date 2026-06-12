from typing import TypedDict, List, Annotated
from langgraph.graph import StateGraph, END

class AbrasiveState(TypedDict):
    material: str
    purity: float
    mesh_size: int
    validation_log: List[str]
    is_approved: bool

def validate_purity(state: AbrasiveState):
    log = state.get("validation_log", [])
    if state.get("purity", 0) >= 98.0:
        log.append("Purity meets industrial standard.")
    else:
        log.append("Purity check failed.")
    return {"validation_log": log}

def check_mesh(state: AbrasiveState):
    log = state.get("validation_log", [])
    if 40 <= state.get("mesh_size", 0) <= 1200:
        log.append("Mesh size is within processing range.")
        is_approved = True
    else:
        log.append("Invalid mesh size for standard application.")
        is_approved = False
    return {"validation_log": log, "is_approved": is_approved}

graph = StateGraph(AbrasiveState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("check_mesh", check_mesh)
graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "check_mesh")
graph.add_edge("check_mesh", END)
graph = graph.compile()
