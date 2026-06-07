from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SteelProcurementState(TypedDict):
    material_grade: str
    quality_docs: List[str]
    is_approved: bool
    error_log: List[str]

def validate_material_specs(state: SteelProcurementState):
    if state.get("material_grade"):
        return {"is_approved": True}
    return {"is_approved": False, "error_log": ["Missing material grade"]}

def verify_quality_docs(state: SteelProcurementState):
    if len(state.get("quality_docs", [])) >= 2:
        return {"is_approved": True}
    return {"is_approved": False, "error_log": ["Insufficient quality documentation"]}

graph = StateGraph(SteelProcurementState)
graph.add_node("validate", validate_material_specs)
graph.add_node("verify", verify_quality_docs)
graph.set_entry_point("validate")
graph.add_edge("validate", "verify")
graph.add_edge("verify", END)
graph = graph.compile()
