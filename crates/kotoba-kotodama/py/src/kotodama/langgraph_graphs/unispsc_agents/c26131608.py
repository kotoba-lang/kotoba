from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class StackProcurementState(TypedDict):
    spec_docs: List[str]
    compliance_validated: bool
    safety_check_passed: bool

async def validate_specs(state: StackProcurementState):
    # Simulate engineering review for flare stack codes
    return {"compliance_validated": True}

async def safety_review(state: StackProcurementState):
    return {"safety_check_passed": True}

graph = StateGraph(StackProcurementState)
graph.add_node("validate", validate_specs)
graph.add_node("safety", safety_review)
graph.set_entry_point("validate")
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph = graph.compile()
