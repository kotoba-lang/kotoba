from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END
import operator

class BearingState(TypedDict):
    spec_data: dict
    validation_results: Annotated[list[str], operator.add]
    is_approved: bool

def validate_bearing_specs(state: BearingState):
    specs = state.get('spec_data', {})
    results = []
    if 'precision_grade' not in specs: results.append('Missing precision grade')
    if 'load_rating_dynamic' not in specs: results.append('Missing load rating')
    return {'validation_results': results, 'is_approved': len(results) == 0}

def route_by_validation(state: BearingState):
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(BearingState)
graph.add_node('validate', validate_bearing_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')
graph = graph.compile()
