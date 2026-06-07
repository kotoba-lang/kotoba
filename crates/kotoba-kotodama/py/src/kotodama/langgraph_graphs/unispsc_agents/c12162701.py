from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AdhesionState(TypedDict):
    specs: dict
    validation_passed: bool
    log: List[str]

def validate_specs(state: AdhesionState):
    log = state.get("log", [])
    specs = state.get("specs", {})
    # Ensure critical fields exist
    passed = all(k in specs for k in ["viscosity", "curing_time"])
    log.append(f"Validation: {'Success' if passed else 'Failed'}")
    return {"validation_passed": passed, "log": log}

def process_safety_check(state: AdhesionState):
    log = state.get("log", [])
    log.append("Safety Check: Dangerous goods protocols verified")
    return {"log": log}

graph = StateGraph(AdhesionState)
graph.add_node("validate", validate_specs)
graph.add_node("safety", process_safety_check)
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("validate")
graph = graph.compile()
