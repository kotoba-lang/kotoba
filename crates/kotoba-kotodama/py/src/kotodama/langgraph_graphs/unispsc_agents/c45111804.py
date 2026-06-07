from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcessingState(TypedDict):
    device_specs: dict
    validation_results: list
    is_approved: bool

def validate_specs(state: ProcessingState):
    specs = state.get('device_specs', {})
    results = []
    if specs.get('latency', 0) > 20:
        results.append('Latency exceeds standard threshold')
    return {'validation_results': results, 'is_approved': len(results) == 0}

graph = StateGraph(ProcessingState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
