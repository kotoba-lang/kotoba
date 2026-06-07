from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class TallowState(TypedDict):
    quality_metrics: dict
    processing_steps: Annotated[list[str], operator.add]
    is_compliant: bool

def validate_tallow_quality(state: TallowState):
    metrics = state.get("quality_metrics", {})
    # Strict adherence to acid and peroxide thresholds
    is_compliant = metrics.get("acid_value", 0) < 2.0 and metrics.get("peroxide_value", 0) < 10.0
    return {"is_compliant": is_compliant, "processing_steps": ["quality_validation_complete"]}

def route_for_processing(state: TallowState):
    return "refining" if state["is_compliant"] else "reject"

graph = StateGraph(TallowState)
graph.add_node("validate", validate_tallow_quality)
graph.add_node("refining", lambda state: {"processing_steps": ["thermal_refining_applied"]})
graph.add_node("reject", lambda state: {"processing_steps": ["disposal_initiated"]})

graph.set_entry_point("validate")
graph.add_conditional_edges("validate", route_for_processing)
graph.add_edge("refining", END)
graph.add_edge("reject", END)

graph = graph.compile()
