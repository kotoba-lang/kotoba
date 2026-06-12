from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class CatalystState(TypedDict):
    material_id: str
    purity_check: bool
    activity_validation: bool
    compliance_tags: Annotated[list, operator.add]

def validate_purity(state: CatalystState):
    # Simulate stringent purity check for metal oxide catalysts
    return {"purity_check": True, "compliance_tags": ["iso_compliance"]}

def validate_activity(state: CatalystState):
    # Simulate catalytic activity simulation
    return {"activity_validation": True, "compliance_tags": ["performance_verified"]}

graph = StateGraph(CatalystState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("validate_activity", validate_activity)
graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "validate_activity")
graph.add_edge("validate_activity", END)
graph = graph.compile()
