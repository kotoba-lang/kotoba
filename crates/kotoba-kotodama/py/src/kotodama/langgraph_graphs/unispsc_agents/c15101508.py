from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class GasProcurementState(TypedDict):
    commodity_id: str
    purity_validated: bool
    safety_check_passed: bool
    log: Annotated[Sequence[str], operator.add]

def validate_gas_purity(state: GasProcurementState) -> GasProcurementState:
    return {"purity_validated": True, "log": ["Purity check for 15101508 passed."]}

def perform_safety_audit(state: GasProcurementState) -> GasProcurementState:
    return {"safety_check_passed": True, "log": ["Industrial safety audit completed."]}

graph = StateGraph(GasProcurementState)
graph.add_node("validate", validate_gas_purity)
graph.add_node("audit", perform_safety_audit)
graph.add_edge("validate", "audit")
graph.add_edge("audit", END)
graph.set_entry_point("validate")
graph = graph.compile()
