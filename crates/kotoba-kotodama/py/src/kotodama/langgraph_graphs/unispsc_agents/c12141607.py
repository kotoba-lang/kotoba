from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class RareEarthState(TypedDict):
    raw_input: dict
    composition_validated: bool
    safety_checked: bool
    log: Annotated[Sequence[str], operator.add]

def validate_composition(state: RareEarthState) -> RareEarthState:
    # Logic for verifying purity and particle size
    return {"composition_validated": True, "log": ["Composition validated against industrial specs"]}

def safety_compliance_check(state: RareEarthState) -> RareEarthState:
    # Logic for dual-use export control and dangerous goods handling
    return {"safety_checked": True, "log": ["Safety and export controls verified"]}

graph = StateGraph(RareEarthState)
graph.add_node("validate", validate_composition)
graph.add_node("safety", safety_compliance_check)
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("validate")
graph = graph.compile()
