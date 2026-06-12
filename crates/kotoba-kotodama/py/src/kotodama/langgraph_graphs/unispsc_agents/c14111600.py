from typing import TypedDict, Annotated, List, Union
from langgraph.graph import StateGraph, END

class PaperState(TypedDict):
    commodity_code: str
    spec_requirements: dict
    validation_logs: List[str]
    approved: bool

def validate_paper_specs(state: PaperState) -> PaperState:
    logs = state.get("validation_logs", [])
    specs = state.get("spec_requirements", {})
    if specs.get("basis_weight_gsm", 0) < 50:
        logs.append("Error: Basis weight below industrial minimum.")
    else:
        logs.append("Quality check passed.")
    return {"validation_logs": logs}

def final_approval(state: PaperState) -> PaperState:
    is_valid = len(state.get("validation_logs", [])) > 0 and "Error" not in str(state["validation_logs"])
    return {"approved": is_valid}

builder = StateGraph(PaperState)
builder.add_node("validate", validate_paper_specs)
builder.add_node("approval", final_approval)
builder.set_entry_point("validate")
builder.add_edge("validate", "approval")
builder.add_edge("approval", END)
graph = builder.compile()
