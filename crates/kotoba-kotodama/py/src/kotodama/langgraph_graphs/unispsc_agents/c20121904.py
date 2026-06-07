from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class SensorState(TypedDict):
    spec_data: dict
    validation_results: List[str]
    is_compliant: bool

def validate_sensor_spec(state: SensorState):
    specs = state.get("spec_data", {})
    results = []
    if specs.get("detection_range_mm", 0) <= 0:
        results.append("Invalid detection range")
    if not specs.get("ingress_protection_rating"):
        results.append("Missing IP rating")
    return {"validation_results": results, "is_compliant": len(results) == 0}

def route_by_compliance(state: SensorState):
    return "compliant_path" if state["is_compliant"] else "manual_review"

graph = StateGraph(SensorState)
graph.add_node("validate", validate_sensor_spec)
graph.add_conditional_edges("validate", route_by_compliance, {"compliant_path": END, "manual_review": END})
graph.set_entry_point("validate")
graph = graph.compile()
