from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BreadProcurementState(TypedDict):
    batch_id: str
    expiry_date: str
    safety_compliant: bool
    status: str

def validate_freshness(state: BreadProcurementState):
    # Business logic for shelf-life verification
    if not state.get('expiry_date'):
        return {"status": "REJECTED_MISSING_DATE"}
    return {"status": "VALIDATED"}

workflow = StateGraph(BreadProcurementState)
workflow.add_node("validate", validate_freshness)
workflow.set_entry_point("validate")
workflow.add_edge("validate", END)
graph = workflow.compile()
