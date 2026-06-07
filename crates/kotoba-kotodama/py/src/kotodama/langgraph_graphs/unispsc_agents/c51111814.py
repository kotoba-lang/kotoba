from typing import TypedDict
from langgraph.graph import StateGraph, END

class DrugProcurementState(TypedDict):
    batch_id: str
    cold_chain_status: bool
    gmp_verified: bool
    cleared: bool

def validate_cold_chain(state: DrugProcurementState):
    return {"cold_chain_status": True}

def verify_gmp_compliance(state: DrugProcurementState):
    return {"gmp_verified": True}

def final_check(state: DrugProcurementState):
    state["cleared"] = state["cold_chain_status"] and state["gmp_verified"]
    return state

builder = StateGraph(DrugProcurementState)
builder.add_node("cold_chain", validate_cold_chain)
builder.add_node("gmp_check", verify_gmp_compliance)
builder.add_node("final", final_check)
builder.set_entry_point("cold_chain")
builder.add_edge("cold_chain", "gmp_check")
builder.add_edge("gmp_check", "final")
builder.add_edge("final", END)
graph = builder.compile()
