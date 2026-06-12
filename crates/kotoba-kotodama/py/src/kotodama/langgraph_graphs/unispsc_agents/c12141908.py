from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalIngestState(TypedDict):
    purity_check_passed: bool
    safety_clearance: bool
    storage_requirements: dict
    workflow_log: Annotated[Sequence[str], operator.add]

def validate_purity(state: ChemicalIngestState):
    # Simulated complex validation for high-purity chemicals
    return {"purity_check_passed": True, "workflow_log": ["Purity validation completed"]}

def check_safety_compliance(state: ChemicalIngestState):
    return {"safety_clearance": True, "workflow_log": ["Safety compliance verified for hazardous material"]}

# Graph definition
graph = StateGraph(ChemicalIngestState)
graph.add_node("validate", validate_purity)
graph.add_node("safety", check_safety_compliance)
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("validate")
graph = graph.compile()
