from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    part_id: str
    spec_requirements: dict
    inspection_results: Annotated[Sequence[str], operator.add]
    is_approved: bool

def validate_specs(state: ProcurementState):
    # Simulate technical validation of components
    results = ["Dimensions verified", "Material certification attached"]
    return {"inspection_results": results, "is_approved": True}

def route_procurement(state: ProcurementState):
    if state.get("is_approved"):
        return "end"
    return "review"

graph = StateGraph(ProcurementState)
graph.add_node("validate", validate_specs)
graph.add_edge("validate", END)
graph.set_entry_point("validate")
graph = graph.compile()
