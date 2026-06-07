from typing import TypedDict
from langgraph.graph import StateGraph, END

class BasterState(TypedDict):
    material_safety_doc: str
    heat_rating: int
    is_compliant: bool

def validate_material(state: BasterState):
    compliant = state.get('material_safety_doc') == 'Certified' and state.get('heat_rating', 0) >= 200
    return {'is_compliant': compliant}

def decision_node(state: BasterState):
    return 'approved' if state['is_compliant'] else 'rejected'

graph = StateGraph(BasterState)
graph.add_node('validate', validate_material)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
