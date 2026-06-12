from langgraph.graph import StateGraph, END
from typing import TypedDict

class CrepeMachineState(TypedDict):
    spec_completed: bool
    safety_verified: bool

def validate_specs(state: CrepeMachineState):
    # Business logic for commercial crepe machine specs
    return {"spec_completed": True}

def verify_safety(state: CrepeMachineState):
    # Verify electrical and hygiene compliance
    return {"safety_verified": True}

graph = StateGraph(CrepeMachineState)
graph.add_node("validate", validate_specs)
graph.add_node("safety", verify_safety)
graph.set_entry_point("validate")
graph.add_edge("validate", "safety")
graph.add_edge("safety", END)
graph = graph.compile()
