from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GalliumState(TypedDict):
    material_id: str
    purity_target: float
    analysis_results: List[dict]
    export_control_flag: bool

def validate_purity(state: GalliumState) -> GalliumState:
    # Logic to check if purity meets semiconductor grade
    return state

def check_dual_use(state: GalliumState) -> GalliumState:
    # Logic for export control compliance
    return state

def finalize_order(state: GalliumState) -> GalliumState:
    return state

graph = StateGraph(GalliumState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("check_dual_use", check_dual_use)
graph.add_node("finalize_order", finalize_order)
graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "check_dual_use")
graph.add_edge("check_dual_use", "finalize_order")
graph.add_edge("finalize_order", END)
graph = graph.compile()
