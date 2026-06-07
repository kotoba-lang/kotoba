from typing import TypedDict
from langgraph.graph import StateGraph, END

class VideoscopeState(TypedDict):
    model_number: str
    is_medical_grade: bool
    inspection_passed: bool

async def validate_specs(state: VideoscopeState):
    # Business logic for videoscope procurement compliance
    return {"inspection_passed": True if state.get("model_number") else False}

def create_graph():
    graph = StateGraph(VideoscopeState)
    graph.add_node("validate", validate_specs)
    graph.set_entry_point("validate")
    graph.add_edge("validate", END)
    return graph.compile()

graph = create_graph()
