from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class RubberSpec(TypedDict):
    material: str
    hardness: float
    dimensions: dict
    approved: bool

def validate_specs(state: RubberSpec):
    # Business logic for rubber angle specification validation
    if not state.get('material'):
        return {"approved": False}
    return {"approved": True}

# LangGraph Workflow setup
graph = StateGraph(RubberSpec)
graph.add_node("validate", validate_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()
