from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    spec_sheet: str
    msds_verified: bool
    torque_range: float
    status: str

def validate_msds(state: ChemicalProcurementState):
    return {"msds_verified": True, "status": "MSDS_VALIDATED"}

def check_torque_compliance(state: ChemicalProcurementState):
    if state.get("torque_range", 0) > 0:
        return {"status": "COMPLIANT"}
    return {"status": "FAIL_TORQUE_MISSING"}

builder = StateGraph(ChemicalProcurementState)
builder.add_node("validate_msds", validate_msds)
builder.add_node("check_spec", check_torque_compliance)
builder.set_entry_point("validate_msds")
builder.add_edge("validate_msds", "check_spec")
builder.add_edge("check_spec", END)
graph = builder.compile()
