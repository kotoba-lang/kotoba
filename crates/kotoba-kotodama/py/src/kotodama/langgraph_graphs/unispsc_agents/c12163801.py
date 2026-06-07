from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class PolymerState(TypedDict):
    material_id: str
    specs: dict
    validation_passed: bool
    error_logs: List[str]

def validate_material(state: PolymerState):
    specs = state.get("specs", {})
    if "tensile_strength_mpa" not in specs:
        return {"validation_passed": False, "error_logs": ["Missing tensile strength"]}
    return {"validation_passed": True}

builder = StateGraph(PolymerState)
builder.add_node("validate", validate_material)
builder.set_entry_point("validate")
builder.add_edge("validate", END)
graph = builder.compile()
