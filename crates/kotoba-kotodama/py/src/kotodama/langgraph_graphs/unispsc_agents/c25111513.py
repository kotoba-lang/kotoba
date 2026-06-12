from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class SeismicVesselState(TypedDict):
    vessel_id: str
    specs: dict
    is_compliant: bool
    validation_log: List[str]

def validate_specs(state: SeismicVesselState):
    specs = state.get('specs', {})
    log = []
    if 'streamer_capacity' not in specs: log.append('Missing streamer capacity')
    return {'is_compliant': len(log) == 0, 'validation_log': log}

def route_by_compliance(state: SeismicVesselState):
    return 'compliant' if state['is_compliant'] else 'non-compliant'

graph = StateGraph(SeismicVesselState)
graph.add_node('validate', validate_specs)
graph.add_conditional_edges('validate', route_by_compliance, {'compliant': END, 'non-compliant': END})
graph.set_entry_point('validate')
graph = graph.compile()
