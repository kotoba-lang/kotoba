from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ReadingKitState(TypedDict):
    kit_id: str
    curriculum_level: str
    validation_errors: List[str]
    is_approved: bool

def validate_curriculum(state: ReadingKitState):
    if state.get("curriculum_level") in ["K-12", "Primary", "Secondary"]:
        return {"is_approved": True}
    return {"validation_errors": ["Invalid curriculum standard"], "is_approved": False}

def finalize_procurement(state: ReadingKitState):
    return {"is_approved": state["is_approved"]}

workflow = StateGraph(ReadingKitState)
workflow.add_node("validate", validate_curriculum)
workflow.add_node("finalize", finalize_procurement)
workflow.set_entry_point("validate")
workflow.add_edge("validate", "finalize")
workflow.add_edge("finalize", END)

graph = workflow.compile()
