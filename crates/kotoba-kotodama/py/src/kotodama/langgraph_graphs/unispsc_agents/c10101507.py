from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
from operator import add

class LivestockState(TypedDict):
    commodity_id: str
    health_status: str
    quarantine_days: int
    compliance_checks: Annotated[Sequence[str], add]

def validate_health(state: LivestockState) -> LivestockState:
    # Logic to verify health certificate existence
    return {'compliance_checks': ['health_validated']}

def check_quarantine(state: LivestockState) -> LivestockState:
    # Logic to determine if quarantine requirements met
    return {'compliance_checks': ['quarantine_passed']}

def route_by_risk(state: LivestockState):
    if state.get('quarantine_days', 0) > 14:
        return 'quarantine_check'
    return 'health_check'

graph = StateGraph(LivestockState)
graph.add_node('health_check', validate_health)
graph.add_node('quarantine_check', check_quarantine)
graph.set_entry_point('health_check')
graph.add_conditional_edges('health_check', route_by_risk)
graph.add_edge('quarantine_check', END)
graph.add_edge('health_check', END)
graph = graph.compile()
