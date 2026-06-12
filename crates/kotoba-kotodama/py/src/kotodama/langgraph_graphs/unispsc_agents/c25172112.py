from typing import TypedDict
from langgraph.graph import StateGraph, END

class VSCState(TypedDict):
    part_number: str
    asil_rating: str
    spec_verified: bool

def validate_asil(state: VSCState):
    return {"spec_verified": state.get("asil_rating") == "D"}

workflow = StateGraph(VSCState)
workflow.add_node("validate_asil", validate_asil)
workflow.set_entry_point("validate_asil")
workflow.add_edge("validate_asil", END)
graph = workflow.compile()
