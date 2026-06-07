from typing import TypedDict
from langgraph.graph import StateGraph, END

class PlotterState(TypedDict):
    pen_type: str
    is_compatible: bool
    validation_passed: bool

def validate_pen_specs(state: PlotterState):
    # Simulate CAD hardware compatibility check
    return {"validation_passed": state.get("is_compatible", False)}

def finalize_procurement(state: PlotterState):
    return {"status": "ready_for_order"}

graph = StateGraph(PlotterState)
graph.add_node("validate", validate_pen_specs)
graph.add_node("finalize", finalize_procurement)
graph.add_edge("validate", "finalize")
graph.set_entry_point("validate")
graph.set_finish_point("finalize")
graph = graph.compile()
