from langgraph.graph import StateGraph, END
from typing import TypedDict

class PrintMakingState(TypedDict):
    material_spec: dict
    validation_passed: bool

def validate_linoleum_specs(state: PrintMakingState):
    spec = state.get('material_spec', {})
    required = ['thickness', 'dimensions']
    passed = all(k in spec for k in required)
    return {'validation_passed': passed}

graph = StateGraph(PrintMakingState)
graph.add_node('validate', validate_linoleum_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
