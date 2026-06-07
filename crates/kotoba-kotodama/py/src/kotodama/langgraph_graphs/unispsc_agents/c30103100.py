from typing import TypedDict
from langgraph.graph import StateGraph, END

class RailProcurementState(TypedDict):
    grade: str
    inspection_report: bool
    approved: bool

def validate_specs(state: RailProcurementState):
    state['approved'] = state.get('grade') == 'UIC 60' and state.get('inspection_report', False)
    return state

def route_procurement(state: RailProcurementState):
    return 'approve' if state['approved'] else 'reject'

graph = StateGraph(RailProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_procurement, {'approve': END, 'reject': END})

graph = graph.compile()
