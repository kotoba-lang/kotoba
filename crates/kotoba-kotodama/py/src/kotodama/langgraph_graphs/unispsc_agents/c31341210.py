from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    part_number: str
    material_certified: bool
    rivet_inspection_passed: bool

def validate_materials(state: AssemblyState):
    return {'material_certified': True}

def inspect_rivets(state: AssemblyState):
    return {'rivet_inspection_passed': True}

graph = StateGraph(AssemblyState)
graph.add_node('validate', validate_materials)
graph.add_node('inspect', inspect_rivets)
graph.add_edge('validate', 'inspect')
graph.add_edge('inspect', END)
graph.set_entry_point('validate')
graph = graph.compile()
