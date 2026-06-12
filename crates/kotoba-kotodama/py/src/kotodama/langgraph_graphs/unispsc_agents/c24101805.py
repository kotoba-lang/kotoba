from typing import TypedDict
from langgraph.graph import StateGraph, END

class DockState(TypedDict):
    spec_data: dict
    validation_results: list

def validate_bumper(state: DockState):
    specs = state.get('spec_data', {})
    results = []
    if specs.get('hardness', 0) < 60:
        results.append('Hardness too low for heavy impact')
    return {'validation_results': results}

def route_verification(state: DockState):
    return 'APPROVED' if not state['validation_results'] else 'REJECT'

graph = StateGraph(DockState)
graph.add_node('validate', validate_bumper)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
