from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages

class MaterialState(TypedDict):
    material_id: str
    purity_check: bool
    safety_clearance: bool
    validation_logs: Annotated[Sequence[str], add_messages]

def validate_purity(state: MaterialState):
    # Simulated complex validation logic for high-purity metals
    is_pure = True
    return {"purity_check": is_pure, "validation_logs": ["Purity validation passed."]}

def check_safety_compliance(state: MaterialState):
    # Simulated dual-use/dangerous goods regulatory check
    is_safe = True
    return {"safety_clearance": is_safe, "validation_logs": ["Safety compliance check cleared."]}

graph = StateGraph(MaterialState)
graph.add_node("validate", validate_purity)
graph.add_node("safety", check_safety_compliance)
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph.set_entry_point("validate")

graph = graph.compile()
