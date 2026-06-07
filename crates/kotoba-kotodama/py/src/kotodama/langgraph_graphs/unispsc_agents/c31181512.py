from typing import TypedDict
from langgraph.graph import StateGraph, END

class GasketState(TypedDict):
    material: str
    pressure: float
    validation_passed: bool

def validate_gasket_specs(state: GasketState):
    # Simulate validation logic for specific physical properties
    if state.get("pressure", 0) > 1000:
        return {"validation_passed": True}
    return {"validation_passed": False}

graph_builder = StateGraph(GasketState)
graph_builder.add_node("validate", validate_gasket_specs)
graph_builder.set_entry_point("validate")
graph_builder.add_edge("validate", END)
graph = graph_builder.compile()
