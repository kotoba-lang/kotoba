from typing import TypedDict
from langgraph.graph import StateGraph, END

class EnlargerState(TypedDict):
    specs: dict
    validation_passed: bool

def validate_optics(state: EnlargerState):
    # Simulate optical alignment check
    specs = state.get('specs', {})
    valid = specs.get('precision_rating', 0) > 90
    return {'validation_passed': valid}

def finalize_build(state: EnlargerState):
    print('Finalizing enlarger assembly and testing workflow.')
    return {'validation_passed': True}

graph = StateGraph(EnlargerState)
graph.add_node('validate', validate_optics)
graph.add_node('finalize', finalize_build)
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('validate')
graph = graph.compile()
