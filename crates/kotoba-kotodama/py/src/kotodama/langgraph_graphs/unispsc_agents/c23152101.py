from typing import TypedDict
from langgraph.graph import StateGraph, END

class BeltState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_belt_specs(state: BeltState):
    specs = state.get('spec_data', {})
    tensile = specs.get('tensile_strength', 0)
    passed = tensile > 500
    return {'validation_passed': passed}

graph = StateGraph(BeltState)
graph.add_node('validate', validate_belt_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
