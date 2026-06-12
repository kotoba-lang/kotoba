from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MineralState(TypedDict):
    raw_material_id: str
    purity_level: float
    compliance_docs: List[str]
    validation_status: str

def validate_material(state: MineralState) -> MineralState:
    if state.get("purity_level", 0) < 95.0:
        return {**state, "validation_status": "FAILED: Low Purity"}
    return {**state, "validation_status": "PASSED: Certified"}

def route_by_status(state: MineralState) -> str:
    if state["validation_status"].startswith("PASSED"):
        return "finalize"
    return "quarantine"

workflow = StateGraph(MineralState)
workflow.add_node("validate", validate_material)
workflow.add_node("finalize", lambda x: x)
workflow.add_node("quarantine", lambda x: x)

workflow.set_entry_point("validate")
workflow.add_conditional_edges("validate", route_by_status, {"finalize": "finalize", "quarantine": "quarantine"})
workflow.add_edge("finalize", END)
workflow.add_edge("quarantine", END)

graph = workflow.compile()
