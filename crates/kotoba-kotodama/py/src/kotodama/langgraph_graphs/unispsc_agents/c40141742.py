from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class AtomizerState(TypedDict):
    spec_data: dict
    validation_passed: bool

def validate_nozzle_specs(state: AtomizerState):
    specs = state.get('spec_data', {})
    required = ['nozzle_material', 'pressure_rating']
    passed = all(key in specs for key in required)
    return {'validation_passed': passed}

graph = StateGraph(AtomizerState)
graph.add_node('validate', validate_nozzle_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
