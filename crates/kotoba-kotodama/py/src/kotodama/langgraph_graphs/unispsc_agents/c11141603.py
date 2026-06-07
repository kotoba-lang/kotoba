from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class SulfurProcurementState(TypedDict):
    batch_id: str
    purity_check: bool
    safety_clearance: bool
    logistics_status: str
    workflow_log: Annotated[Sequence[str], operator.add]

def validate_purity(state: SulfurProcurementState):
    # Simulate purity validation for industrial sulfur
    return {"purity_check": True, "workflow_log": ["Purity verified against spec"]}

def check_safety_compliance(state: SulfurProcurementState):
    # Simulate dangerous goods compliance check
    return {"safety_clearance": True, "workflow_log": ["Chemical safety and hazardous handling verified"]}

workflow = StateGraph(SulfurProcurementState)
workflow.add_node("validate_purity", validate_purity)
workflow.add_node("check_safety", check_safety_compliance)
workflow.set_entry_point("validate_purity")
workflow.add_edge("validate_purity", "check_safety")
workflow.add_edge("check_safety", END)
graph = workflow.compile()
