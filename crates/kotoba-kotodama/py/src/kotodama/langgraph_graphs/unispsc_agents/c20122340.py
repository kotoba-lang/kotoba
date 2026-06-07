from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class RobotAssemblyState(TypedDict):
    part_id: str
    specs: dict
    validation_log: List[str]
    is_approved: bool

def validate_structural_specs(state: RobotAssemblyState):
    specs = state.get("specs", {})
    log = []
    if specs.get("tensile_strength_mpa", 0) < 200:
        log.append("Failed: Tensile strength insufficient for structural use.")
    return {"validation_log": log, "is_approved": len(log) == 0}

def structural_integrity_check(state: RobotAssemblyState):
    log = state.get("validation_log", [])
    if state.get("is_approved"):
        log.append("Structural integrity validated for robot chassis.")
    return {"validation_log": log}

graph = StateGraph(RobotAssemblyState)
graph.add_node("validate_specs", validate_structural_specs)
graph.add_node("check_integrity", structural_integrity_check)
graph.set_entry_point("validate_specs")
graph.add_edge("validate_specs", "check_integrity")
graph.add_edge("check_integrity", END)
graph = graph.compile()
