from typing import TypedDict
from langgraph.graph import StateGraph, END

class BreadGuideState(TypedDict):
    material_certified: bool
    stability_score: float
    meets_dimensions: bool

def validate_materials(state: BreadGuideState):
    state['material_certified'] = True
    return state

def check_stability(state: BreadGuideState):
    state['stability_score'] = 9.5
    return state

graph = StateGraph(BreadGuideState)
graph.add_node('material_check', validate_materials)
graph.add_node('stability_check', check_stability)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'stability_check')
graph.add_edge('stability_check', END)
graph = graph.compile()
