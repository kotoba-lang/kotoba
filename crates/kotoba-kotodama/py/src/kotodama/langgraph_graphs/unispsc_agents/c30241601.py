from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GrandstandState(TypedDict):
    material_spec: str
    safety_rating: str
    compliance_checked: bool

def validate_materials(state: GrandstandState):
    return {"compliance_checked": state.get("material_spec") == "ASTM-compliant"}

workflow = StateGraph(GrandstandState)
workflow.add_node("validate_materials", validate_materials)
workflow.set_entry_point("validate_materials")
workflow.add_edge("validate_materials", END)
graph = workflow.compile()
