from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ShoeSourcingState(TypedDict):
    specs: dict
    validation_results: List[str]
    approved: bool

def validate_materials(state: ShoeSourcingState):
    # Simulate material safety check
    return {'validation_results': ['Material compliance check: Passed']}

def check_sizing_standards(state: ShoeSourcingState):
    # Simulate sizing verification
    return {'validation_results': state['validation_results'] + ['Sizing standard: Verified']}

graph = StateGraph(ShoeSourcingState)
graph.add_node('material_check', validate_materials)
graph.add_node('sizing_check', check_sizing_standards)
graph.add_edge('material_check', 'sizing_check')
graph.add_edge('sizing_check', END)
graph.set_entry_point('material_check')
graph = graph.compile()
