from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class CrepePaperState(TypedDict):
    spec_data: dict
    validation_logs: List[str]
    is_compliant: bool

def validate_specs(state: CrepePaperState):
    specs = state.get("spec_data", {})
    logs = []
    if specs.get("basis_weight_gsm", 0) < 30:
        logs.append("Basis weight too low for industrial grade")
    return {"validation_logs": logs, "is_compliant": len(logs) == 0}

def route_by_compliance(state: CrepePaperState):
    return "approved" if state["is_compliant"] else "rejected"

builder = StateGraph(CrepePaperState)
builder.add_node("validate", validate_specs)
builder.set_entry_point("validate")
builder.add_conditional_edges("validate", route_by_compliance, {"approved": END, "rejected": END})
graph = builder.compile()
