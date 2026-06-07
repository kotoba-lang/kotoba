from typing import TypedDict
from langgraph.graph import StateGraph, END

class ShavingCutterState(TypedDict):
    spec_check: bool
    is_compliant: bool

def validate_specs(state: ShavingCutterState):
    # Simulate CAD/Spec validation logic
    return {"is_compliant": True}

def export_review(state: ShavingCutterState):
    # Check ECCN export control status
    return {"spec_check": True}

graph = StateGraph(ShavingCutterState)
graph.add_node("validate", validate_specs)
graph.add_node("export", export_review)
graph.set_entry_point("export")
graph.add_edge("export", "validate")
graph.add_edge("validate", END)
graph = graph.compile()
