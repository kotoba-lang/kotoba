from typing import TypedDict
from langgraph.graph import StateGraph, END

class BoomwhackerState(TypedDict):
    material_certified: bool
    tuning_verified: bool
    is_compliant: bool

def check_material(state: BoomwhackerState):
    return {'material_certified': True}

def verify_tuning(state: BoomwhackerState):
    return {'tuning_verified': True}

def finalize_compliance(state: BoomwhackerState):
    compliant = state['material_certified'] and state['tuning_verified']
    return {'is_compliant': compliant}

graph = StateGraph(BoomwhackerState)
graph.add_node('material', check_material)
graph.add_node('tuning', verify_tuning)
graph.add_node('compliance', finalize_compliance)
graph.set_entry_point('material')
graph.add_edge('material', 'tuning')
graph.add_edge('tuning', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
