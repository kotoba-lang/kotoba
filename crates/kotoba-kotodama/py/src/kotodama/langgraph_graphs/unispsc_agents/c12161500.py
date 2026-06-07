from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ChemicalState(TypedDict):
    material_id: str
    compliance_score: float
    hazard_check_passed: bool
    history: Annotated[Sequence[str], operator.add]

def validate_purity(state: ChemicalState):
    # Simulate purity validation logic for chemicals
    return {"compliance_score": 0.95, "history": ["Purity validated"]}

def check_hazards(state: ChemicalState):
    # Simulate hazard check and regulatory screening
    return {"hazard_check_passed": True, "history": ["Hazard screening complete"]}

workflow = StateGraph(ChemicalState)
workflow.add_node("purity_check", validate_purity)
workflow.add_node("hazard_check", check_hazards)
workflow.add_edge("purity_check", "hazard_check")
workflow.add_edge("hazard_check", END)
workflow.set_entry_point("purity_check")
graph = workflow.compile()
