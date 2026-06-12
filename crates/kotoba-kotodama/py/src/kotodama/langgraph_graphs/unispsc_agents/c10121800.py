from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class LivestockState(TypedDict):
    commodity_id: str
    health_status: str
    quarantine_verified: bool
    inspection_passed: bool
    log: List[str]

def validate_health_status(state: LivestockState):
    # Simulate health check logic
    status = state.get('health_status', 'pending')
    return {'quarantine_verified': status == 'certified', 'log': ['Health check initialized']}

def perform_inspection(state: LivestockState):
    # Simulate physical inspection
    return {'inspection_passed': True, 'log': state['log'] + ['Inspection completed']}

def build_livestock_graph():
    graph = StateGraph(LivestockState)
    graph.add_node('health_check', validate_health_status)
    graph.add_node('inspection', perform_inspection)
    graph.set_entry_point('health_check')
    graph.add_edge('health_check', 'inspection')
    graph.add_edge('inspection', END)
    return graph.compile()

graph = build_livestock_graph()
