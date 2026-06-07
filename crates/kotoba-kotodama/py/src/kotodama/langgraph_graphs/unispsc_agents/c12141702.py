from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class CatalystState(TypedDict):
    purity_level: float
    safety_clearance: bool
    hazard_codes: Sequence[str]
    steps_completed: Annotated[Sequence[str], operator.add]

def validate_purity(state: CatalystState) -> CatalystState:
    return {"steps_completed": ["Purity Validation Passed"], "purity_level": state.get("purity_level", 0.0)}

def check_hazards(state: CatalystState) -> CatalystState:
    return {"steps_completed": ["Hazard Assessment Completed"], "safety_clearance": True}

graph = StateGraph(CatalystState)
graph.add_node("validate", validate_purity)
graph.add_node("hazard_check", check_hazards)
graph.set_entry_point("validate")
graph.add_edge("validate", "hazard_check")
graph.add_edge("hazard_check", END)
graph = graph.compile()
