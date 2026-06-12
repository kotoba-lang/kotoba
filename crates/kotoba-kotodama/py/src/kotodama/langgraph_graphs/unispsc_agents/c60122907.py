from typing import TypedDict
from langgraph.graph import StateGraph, END

class BeadState(TypedDict):
    material_check: bool
    safety_compliant: bool
    final_approved: bool

def validate_material(state: BeadState):
    state['material_check'] = True
    return state

def check_toxicity(state: BeadState):
    state['safety_compliant'] = True
    return state

graph = StateGraph(BeadState)
graph.add_node('material', validate_material)
graph.add_node('safety', check_toxicity)
graph.set_entry_point('material')
graph.add_edge('material', 'safety')
graph.add_edge('safety', END)

graph = graph.compile()
