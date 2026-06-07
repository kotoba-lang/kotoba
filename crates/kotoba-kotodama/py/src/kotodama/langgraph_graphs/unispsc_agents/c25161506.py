from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BikeProcurementState(TypedDict):
    bike_id: str
    spec_sheet: dict
    validation_results: List[str]
    approved: bool

def validate_specs(state: BikeProcurementState):
    specs = state.get('spec_sheet', {})
    results = []
    if specs.get('weight_kg', 10) > 8:
        results.append('Weight exceeds racing threshold')
    return {'validation_results': results, 'approved': len(results) == 0}

def route_by_validation(state: BikeProcurementState):
    return 'approved' if state['approved'] else 'rejected'

graph = StateGraph(BikeProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
