from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
import operator

class LivestockState(TypedDict):
    commodity_code: str
    inspection_status: bool
    compliance_checks: Annotated[List[str], operator.add]
    is_approved: bool

def validate_livestock_batch(state: LivestockState):
    checks = state.get('compliance_checks', [])
    is_valid = len(checks) >= 3
    return {'is_approved': is_valid}

def perform_inspection(state: LivestockState):
    return {'inspection_status': True, 'compliance_checks': ['sanitary_check', 'origin_verification']}

def complete_procurement(state: LivestockState):
    return {'compliance_checks': ['procurement_finalized']}

graph = StateGraph(LivestockState)
graph.add_node('inspect', perform_inspection)
graph.add_node('validate', validate_livestock_batch)
graph.add_node('finalize', complete_procurement)
graph.add_edge('inspect', 'validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph.set_entry_point('inspect')
graph = graph.compile()
