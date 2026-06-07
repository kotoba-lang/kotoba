from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from operator import add

class OilGasState(TypedDict):
    commodity_id: str
    purity_check: bool
    safety_compliance: bool
    logistics_status: str
    process_steps: Annotated[Sequence[str], add]

def validate_purity(state: OilGasState):
    return {"purity_check": True, "process_steps": ["Purity validation complete"]}

def perform_safety_audit(state: OilGasState):
    return {"safety_compliance": True, "process_steps": ["Safety audit cleared"]}

def update_logistics(state: OilGasState):
    return {"logistics_status": "Ready for transport", "process_steps": ["Logistics updated"]}

graph = StateGraph(OilGasState)
graph.add_node("purity", validate_purity)
graph.add_node("safety", perform_safety_audit)
graph.add_node("logistics", update_logistics)
graph.set_entry_point("purity")
graph.add_edge("purity", "safety")
graph.add_edge("safety", "logistics")
graph.add_edge("logistics", END)
graph = graph.compile()
