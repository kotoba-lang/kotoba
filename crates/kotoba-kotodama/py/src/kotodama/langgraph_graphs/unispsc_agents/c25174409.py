from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class VisorState(TypedDict):
    part_specs: dict
    validation_passed: bool

def validate_specs(state: VisorState):
    specs = state.get('part_specs', {})
    required = ['flammability', 'dimensions']
    return {'validation_passed': all(k in specs for k in required)}

def finalize_order(state: VisorState):
    return {'validation_passed': True}

graph = StateGraph(VisorState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
