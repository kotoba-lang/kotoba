from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class AmpouleState(TypedDict):
    specifications: dict
    validation_passed: bool
    error_logs: List[str]

def validate_ampoule_specs(state: AmpouleState):
    specs = state.get("specifications", {})
    required = ["material", "sterility_cert", "break_force"]
    errors = [key for key in required if key not in specs]
    return {"validation_passed": len(errors) == 0, "error_logs": errors}

def route_by_validation(state: AmpouleState):
    return "passed" if state["validation_passed"] else "failed"

graph = StateGraph(AmpouleState)
graph.add_node("validate", validate_ampoule_specs)
graph.add_conditional_edges("validate", route_by_validation, {"passed": END, "failed": END})
graph.set_entry_point("validate")
graph = graph.compile()
