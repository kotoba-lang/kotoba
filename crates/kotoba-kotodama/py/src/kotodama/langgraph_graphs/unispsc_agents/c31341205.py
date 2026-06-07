from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    material_grade: str
    rivet_compliance: bool
    dimensional_check: bool

def validate_materials(state: AssemblyState):
    print('Validating low alloy steel grade...')
    return {'material_grade': 'verified'}

def inspect_rivets(state: AssemblyState):
    print('Checking rivet fastening standards...')
    return {'rivet_compliance': True}

graph = StateGraph(AssemblyState)
graph.add_node('material', validate_materials)
graph.add_node('rivets', inspect_rivets)
graph.set_entry_point('material')
graph.add_edge('material', 'rivets')
graph.add_edge('rivets', END)
graph = graph.compile()
