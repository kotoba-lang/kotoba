from typing import TypedDict
from langgraph.graph import StateGraph, END

class BenchSpecState(TypedDict):
    material: str
    stability_score: float
    approved: bool

def validate_bench_specs(state: BenchSpecState):
    if state.get("material") in ["hardwood", "steel"] and state.get("stability_score", 0) > 8.0:
        return {"approved": True}
    return {"approved": False}

graph = StateGraph(BenchSpecState)
graph.add_node("validate", validate_bench_specs)
graph.set_entry_point("validate")
graph.add_edge("validate", END)
graph = graph.compile()
