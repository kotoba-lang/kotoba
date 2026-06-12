from typing import TypedDict
from langgraph.graph import StateGraph, END

class CrystalState(TypedDict):
    spec_data: dict
    validation_score: float
    status: str

def validate_crystal_specs(state: CrystalState):
    specs = state.get('spec_data', {})
    score = 0.0
    if 'refractive_index' in specs: score += 0.5
    if 'clarity' in specs: score += 0.5
    return {'validation_score': score, 'status': 'validated' if score >= 1.0 else 'rejected'}

graph = StateGraph(CrystalState)
graph.add_node('validator', validate_crystal_specs)
graph.set_entry_point('validator')
graph.add_edge('validator', END)
graph = graph.compile()
