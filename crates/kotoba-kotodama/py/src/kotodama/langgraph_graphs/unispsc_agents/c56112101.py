from typing import TypedDict
from langgraph.graph import StateGraph, END

class SeatingProcurementState(TypedDict):
    spec_data: dict
    validation_results: list
    is_approved: bool

def validate_seating_specs(state: SeatingProcurementState):
    specs = state.get('spec_data', {})
    results = []
    if specs.get('fire_safety_certification'):
        results.append('Safety compliant')
    else:
        results.append('Missing safety certification')
    return {'validation_results': results, 'is_approved': len(results) == 1}

graph = StateGraph(SeatingProcurementState)
graph.add_node('validate', validate_seating_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
