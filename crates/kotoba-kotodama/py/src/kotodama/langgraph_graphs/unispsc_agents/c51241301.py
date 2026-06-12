from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    material_id: str
    purity_validated: bool
    sds_verified: bool
    hazard_check: bool

def validate_purity(state: ChemicalProcurementState):
    return {"purity_validated": True}

def verify_sds(state: ChemicalProcurementState):
    return {"sds_verified": True}

graph = StateGraph(ChemicalProcurementState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("verify_sds", verify_sds)
graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "verify_sds")
graph.add_edge("verify_sds", END)
graph = graph.compile()
