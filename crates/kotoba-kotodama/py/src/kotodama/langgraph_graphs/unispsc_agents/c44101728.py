from typing import TypedDict
from langgraph.graph import StateGraph, END

class RollFeedState(TypedDict):
    spec_sheet: dict
    validation_results: dict

def validate_specs(state: RollFeedState):
    specs = state.get('spec_sheet', {})
    # Logic to validate feed precision and load capacity limits
    is_valid = specs.get('precision', 0) <= 0.05
    return {'validation_results': {'is_valid': is_valid}}

def route_by_validation(state: RollFeedState):
    return 'approved' if state['validation_results']['is_valid'] else 'rejected'

graph = StateGraph(RollFeedState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
