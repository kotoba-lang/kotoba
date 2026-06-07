from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    commodity_code: str
    purity_level: float
    origin: str
    traceability_data: dict
    approved: bool
    validation_log: List[str]

def validate_purity(state: MineralState):
    log = state.get("validation_log", [])
    if state.get("purity_level", 0) >= 95.0:
        log.append("Purity standard met.")
        return {"approved": True, "validation_log": log}
    log.append("Purity insufficient for high-grade processing.")
    return {"approved": False, "validation_log": log}

def check_sanctions(state: MineralState):
    log = state.get("validation_log", [])
    if state.get("origin") in ["restricted_zone_a", "restricted_zone_b"]:
        log.append("Origin flagged for sanction review.")
        return {"approved": False, "validation_log": log}
    log.append("Origin passed compliance screening.")
    return {"approved": True, "validation_log": log}

graph = StateGraph(MineralState)
graph.add_node("validate", validate_purity)
graph.add_node("compliance", check_sanctions)
graph.add_edge("compliance", "validate")
graph.add_edge("validate", END)
graph.set_entry_point("compliance")
graph = graph.compile()
