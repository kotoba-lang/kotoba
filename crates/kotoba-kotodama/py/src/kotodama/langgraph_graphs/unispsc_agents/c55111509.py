from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class BGMState(TypedDict):
    license_type: str
    coverage_zones: List[str]
    compliance_status: bool

def validate_license(state: BGMState):
    state['compliance_status'] = state.get('license_type') == 'commercial'
    return state

def route_distribution(state: BGMState):
    return 'process_stream' if state['compliance_status'] else 'reject'

graph = StateGraph(BGMState)
graph.add_node('validate', validate_license)
graph.add_node('process_stream', lambda x: x)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process_stream')
graph.add_edge('process_stream', END)

graph = graph.compile()
