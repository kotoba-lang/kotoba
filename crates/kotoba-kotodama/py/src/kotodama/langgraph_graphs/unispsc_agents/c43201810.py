from langgraph.graph import StateGraph, END
from typing import TypedDict
class DVDProcurementState(TypedDict):
    capacity_gb: int
    verification_status: bool
    approved: bool
def validate_specs(state: DVDProcurementState):
    state['verification_status'] = state.get('capacity_gb', 0) > 0
    return {'verification_status': state['verification_status']}
def finalize_order(state: DVDProcurementState):
    state['approved'] = state['verification_status']
    return {'approved': state['approved']}
graph = StateGraph(DVDProcurementState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
