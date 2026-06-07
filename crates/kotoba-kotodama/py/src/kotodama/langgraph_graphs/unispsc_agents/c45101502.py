from typing import TypedDict
from langgraph.graph import StateGraph, END

class PrintingPressState(TypedDict):
    spec_data: dict
    validation_results: list
    is_approved: bool

def validate_specs(state):
    specs = state.get('spec_data', {})
    results = []
    if specs.get('power_consumption_kwh', 0) > 500:
        results.append('High power requirement flagged')
    return {'validation_results': results, 'is_approved': len(results) == 0}

graph = StateGraph(PrintingPressState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
