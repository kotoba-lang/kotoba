from typing import TypedDict
from langgraph.graph import StateGraph, END

class SpiceState(TypedDict):
    inspection_passed: bool
    compliance_docs: list
    shipping_status: str

def validate_quality(state: SpiceState):
    """Validates spice batch compliance documents."""
    docs = state.get('compliance_docs', [])
    passed = 'haccp' in [d.lower() for d in docs] and 'pesticide_report' in [d.lower() for d in docs]
    return {'inspection_passed': passed}

def route_shipping(state: SpiceState):
    return 'approved' if state['inspection_passed'] else 'rejected'

graph = StateGraph(SpiceState)
graph.add_node('validate', validate_quality)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_shipping, {'approved': END, 'rejected': END})
graph = graph.compile()
