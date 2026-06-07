from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class CoalProcurementState(TypedDict):
    requirements: dict
    inspection_results: Annotated[Sequence[dict], operator.add]
    is_approved: bool

def validate_quality(state: CoalProcurementState):
    # Business logic for coal quality validation
    quality = state.get('requirements', {}).get('calorific_value', 0)
    return {'inspection_results': [{'status': 'passed' if quality > 6000 else 'failed'}]}

def approve_procurement(state: CoalProcurementState):
    # Approve if all inspections passed
    passed = all(res['status'] == 'passed' for res in state['inspection_results'])
    return {'is_approved': passed}

graph = StateGraph(CoalProcurementState)
graph.add_node('validate', validate_quality)
graph.add_node('approve', approve_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
