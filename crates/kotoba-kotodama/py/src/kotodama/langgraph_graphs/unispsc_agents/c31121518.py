from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    material_certified: bool
    dimensional_check_passed: bool

def validate_composition(state: CastState):
    return {'material_certified': True}

def perform_dimensional_analysis(state: CastState):
    return {'dimensional_check_passed': True}

graph = StateGraph(CastState)
graph.add_node('validate', validate_composition)
graph.add_node('inspection', perform_dimensional_analysis)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inspection')
graph.add_edge('inspection', END)
graph = graph.compile()
