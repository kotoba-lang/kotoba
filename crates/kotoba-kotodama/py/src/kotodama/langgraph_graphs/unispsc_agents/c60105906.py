from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EducationMaterialState(TypedDict):
    material_id: str
    clinical_approval_status: bool
    media_format: str
    content_review_required: bool

def validate_content(state: EducationMaterialState):
    # Simulated validation logic for medical content accuracy
    return {"clinical_approval_status": True}

def format_package(state: EducationMaterialState):
    return {"content_review_required": False}

graph = StateGraph(EducationMaterialState)
graph.add_node("validate", validate_content)
graph.add_node("format", format_package)
graph.set_entry_point("validate")
graph.add_edge("validate", "format")
graph.add_edge("format", END)
graph = graph.compile()
