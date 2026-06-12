from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class WeldingPowderState(TypedDict):
    material_id: str
    purity_check: bool
    particle_analysis: List[float]
    is_approved: bool

def validate_composition(state: WeldingPowderState):
    # Simulate chemical purity validation
    return {"purity_check": True}

def analyze_particles(state: WeldingPowderState):
    # Simulate particle distribution check
    return {"particle_analysis": [15.5, 20.2, 14.8]}

def finalize_approval(state: WeldingPowderState):
    approved = state["purity_check"] and len(state["particle_analysis"]) > 0
    return {"is_approved": approved}

graph = StateGraph(WeldingPowderState)
graph.add_node("validate", validate_composition)
graph.add_node("analyze", analyze_particles)
graph.add_node("approve", finalize_approval)
graph.set_entry_point("validate")
graph.add_edge("validate", "analyze")
graph.add_edge("analyze", "approve")
graph.add_edge("approve", END)
graph = graph.compile()
