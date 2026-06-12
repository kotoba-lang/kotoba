from typing import TypedDict
from langgraph.graph import StateGraph, END

class ResusCaseState(TypedDict):
    case_model: str
    material_compliance: bool
    is_sterile_pack: bool

def validate_materials(state: ResusCaseState):
    return {"material_compliance": True}

def check_regulatory(state: ResusCaseState):
    return {"is_sterile_pack": True}

graph = StateGraph(ResusCaseState)
graph.add_node("material_check", validate_materials)
graph.add_node("regulatory_check", check_regulatory)
graph.set_entry_point("material_check")
graph.add_edge("material_check", "regulatory_check")
graph.add_edge("regulatory_check", END)
graph = graph.compile()
