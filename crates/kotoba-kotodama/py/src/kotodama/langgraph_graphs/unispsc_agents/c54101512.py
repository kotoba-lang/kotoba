from typing import TypedDict
from langgraph.graph import StateGraph, END

class JewelryState(TypedDict):
    material_certified: bool
    purity_check: float
    dimensions_ok: bool

def validate_materials(state: JewelryState):
    return {'material_certified': True}

def quality_control(state: JewelryState):
    return {'dimensions_ok': state.get('purity_check', 0) >= 0.99}

graph = StateGraph(JewelryState)
graph.add_node('validate', validate_materials)
graph.add_node('qc', quality_control)
graph.add_edge('validate', 'qc')
graph.add_edge('qc', END)
graph.set_entry_point('validate')
graph = graph.compile()
