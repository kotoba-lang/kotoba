from typing import TypedDict
from langgraph.graph import StateGraph

class TankCoverState(TypedDict):
    dimensions: dict
    model_match: bool
    approved: bool

def validate_dimensions(state: TankCoverState):
    """Validate physical dimensions against model specifications."""
    print("Validating dimensions...")
    return {"approved": state.get("model_match", False)}

graph = StateGraph(TankCoverState)
graph.add_node("validate", validate_dimensions)
graph.set_entry_point("validate")
graph.set_finish_point("validate")
graph = graph.compile()
