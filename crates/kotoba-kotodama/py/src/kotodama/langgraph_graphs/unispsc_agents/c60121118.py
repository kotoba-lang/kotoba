from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class PackagingState(TypedDict):
    material_type: str
    spec_requirements: dict
    validation_passed: bool

def validate_craft_specs(state: PackagingState):
    specs = state.get('spec_requirements', {})
    required = ['basis_weight_gsm', 'flute_type']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def route_by_validation(state: PackagingState):
    return 'validate' if not state.get('validation_passed') else END

graph = StateGraph(PackagingState)
graph.add_node('validate', validate_craft_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
