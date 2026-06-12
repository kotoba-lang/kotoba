from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ExtractionState(TypedDict):
    material_specs: dict
    validation_log: List[str]
    is_approved: bool

def validate_specs(state: ExtractionState):
    log = state.get("validation_log", [])
    specs = state.get("material_specs", {})
    if specs.get("tensile_strength", 0) > 800:
        log.append("Strength verified for deep drilling.")
    else:
        log.append("Strength insufficient.")
    return {"validation_log": log}

def approval_check(state: ExtractionState):
    return "approved" if "Strength verified for deep drilling." in state.get("validation_log", []) else "rejected"

builder = StateGraph(ExtractionState)
builder.add_node("validate", validate_specs)
builder.add_edge("validate", END)
builder.set_entry_point("validate")
graph = builder.compile()
