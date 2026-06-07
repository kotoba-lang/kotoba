from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    material_certified: bool
    welding_tested: bool
    approved: bool

def validate_material(state: AssemblyState):
    state['material_certified'] = True
    return state

def validate_welding(state: AssemblyState):
    state['welding_tested'] = True
    return state

def check_compliance(state: AssemblyState):
    state['approved'] = state['material_certified'] and state['welding_tested']
    return state

graph = StateGraph(AssemblyState)
graph.add_node('material', validate_material)
graph.add_node('welding', validate_welding)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('material')
graph.add_edge('material', 'welding')
graph.add_edge('welding', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
