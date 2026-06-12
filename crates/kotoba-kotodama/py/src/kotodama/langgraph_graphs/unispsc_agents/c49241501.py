from typing import TypedDict
from langgraph.graph import StateGraph, END

class PlaygroundState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_safety_compliance(state: PlaygroundState):
    # Business logic for EN 1176 playground equipment compliance check
    specs = state.get('spec_data', {})
    compliant = specs.get('certified', False) and specs.get('impact_test_passed', False)
    return {'is_compliant': compliant}

def finalize_spec(state: PlaygroundState):
    return {'status': 'READY_FOR_RFQ'}

graph = StateGraph(PlaygroundState)
graph.add_node('validate', validate_safety_compliance)
graph.add_node('format', finalize_spec)
graph.add_edge('validate', 'format')
graph.add_edge('format', END)
graph.set_entry_point('validate')
graph = graph.compile()
