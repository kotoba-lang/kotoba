from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class TractionState(TypedDict):
    part_number: str
    compliance_checklist: List[str]
    approved: bool

def validate_traction_specs(state: TractionState):
    # Simulate regulatory compliance checks
    compliance = ["ISO_13485", "CE_Mark"]
    return {"compliance_checklist": compliance, "approved": len(compliance) >= 2}

graph = StateGraph(TractionState)
graph.add_node("validate", validate_traction_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()
