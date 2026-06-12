from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ZirconiaState(TypedDict):
    purity_cert: str
    particle_analysis: dict
    approved: bool

def validate_purity(state: ZirconiaState):
    # Simulate chemical validation logic
    is_pure = float(state.get('purity_cert', 0)) >= 99.9
    return {"approved": is_pure}

def process_particle_spec(state: ZirconiaState):
    # Simulate particle distribution analysis
    return {"particle_analysis": {"status": "verified"}}

graph = StateGraph(ZirconiaState)
graph.add_node("validate", validate_purity)
graph.add_node("analyze", process_particle_spec)
graph.set_entry_point("validate")
graph.add_edge("validate", "analyze")
graph.add_edge("analyze", END)
graph = graph.compile()
