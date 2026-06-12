from typing import TypedDict
from langgraph.graph import StateGraph, END

class PipeAssemblyState(TypedDict):
    material_certified: bool
    weld_validated: bool
    leak_test_passed: bool

def validate_materials(state: PipeAssemblyState):
    return {'material_certified': True}

def inspect_welds(state: PipeAssemblyState):
    return {'weld_validated': True}

def perform_leak_test(state: PipeAssemblyState):
    return {'leak_test_passed': True}

graph = StateGraph(PipeAssemblyState)
graph.add_node('material', validate_materials)
graph.add_node('weld', inspect_welds)
graph.add_node('test', perform_leak_test)
graph.set_entry_point('material')
graph.add_edge('material', 'weld')
graph.add_edge('weld', 'test')
graph.add_edge('test', END)
graph = graph.compile()
