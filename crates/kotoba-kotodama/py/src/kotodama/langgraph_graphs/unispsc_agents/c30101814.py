from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    lead_certified: bool
    compliance_docs: List[str]
    status: str

def validate_hazardous_material(state: ProcurementState):
    if state.get("lead_certified"):
        return {"status": "APPROVED"}
    return {"status": "REJECTED_MISSING_CERT"}

workflow = StateGraph(ProcurementState)
workflow.add_node("validate_lead", validate_hazardous_material)
workflow.set_entry_point("validate_lead")
workflow.add_edge("validate_lead", END)
graph = workflow.compile()
