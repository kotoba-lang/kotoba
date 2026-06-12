from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    purity: float
    gmp_compliant: bool
    temp_log_verified: bool

def validate_purity(state: PharmState):
    return {"purity": state.get("purity", 0.0) >= 99.0}

def check_compliance(state: PharmState):
    return {"gmp_compliant": True}

workflow = StateGraph(PharmState)
workflow.add_node("validate", validate_purity)
workflow.add_node("compliance", check_compliance)
workflow.add_edge("validate", "compliance")
workflow.add_edge("compliance", END)
workflow.set_entry_point("validate")
graph = workflow.compile()
