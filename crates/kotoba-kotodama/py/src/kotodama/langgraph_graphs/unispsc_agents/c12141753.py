from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    commodity_code: str
    purity_level: float
    safety_clearance: bool
    inspection_log: List[str]

def validate_purity(state: ChemicalProcurementState):
    log = state.get("inspection_log", [])
    if state.get("purity_level", 0) < 99.0:
        log.append("Purity below industrial threshold. Flagging for review.")
    else:
        log.append("Purity verified.")
    return {"inspection_log": log}

def check_compliance(state: ChemicalProcurementState):
    log = state.get("inspection_log", [])
    if not state.get("safety_clearance", False):
        log.append("Safety clearance missing. Approval denied.")
    return {"inspection_log": log}

graph = StateGraph(ChemicalProcurementState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("check_compliance", check_compliance)
graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "check_compliance")
graph.add_edge("check_compliance", END)
graph = graph.compile()
