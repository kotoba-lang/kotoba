from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CropProcurementState(TypedDict):
    crop_id: str
    quality_metrics: dict
    inspection_status: str
    approval_path: Sequence[str]

def validate_metrics(state: CropProcurementState):
    # Simulate validation logic for crop quality
    metrics = state.get("quality_metrics", {})
    status = "APPROVED" if metrics.get("purity", 0) > 95 else "REJECTED"
    return {"inspection_status": status}

def route_procurement(state: CropProcurementState):
    return "end" if state["inspection_status"] == "APPROVED" else "review"

workflow = StateGraph(CropProcurementState)
workflow.add_node("validate", validate_metrics)
workflow.add_edge("validate", END)
workflow.set_entry_point("validate")
graph = workflow.compile()
