from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CatalystState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    process_steps: Annotated[Sequence[str], operator.add]

def validate_catalyst(state: CatalystState):
    # Simulated validation logic for chemical purity
    return {"purity_check": True, "process_steps": ["Purity validation complete"]}

def safety_protocol(state: CatalystState):
    # Simulated safety clearance workflow
    return {"safety_clearance": True, "process_steps": ["MSDS and safety protocol cleared"]}

graph = StateGraph(CatalystState)
graph.add_node("validate", validate_catalyst)
graph.add_node("safety", safety_protocol)
graph.set_entry_point("validate")
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph = graph.compile()
