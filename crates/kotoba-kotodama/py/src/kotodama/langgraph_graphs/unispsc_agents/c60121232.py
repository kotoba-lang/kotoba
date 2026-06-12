from typing import TypedDict
from langgraph.graph import StateGraph, END

class PrintingToolState(TypedDict):
    tool_id: str
    spec_check: bool
    approved: bool

def validate_roller(state: PrintingToolState):
    # Simulate CAD/spec validation for brayer geometry
    return {"spec_check": True}

def approve_procurement(state: PrintingToolState):
    return {"approved": True}

graph = StateGraph(PrintingToolState)
graph.add_node("validate", validate_roller)
graph.add_node("approve", approve_procurement)
graph.set_entry_point("validate")
graph.add_edge("validate", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
