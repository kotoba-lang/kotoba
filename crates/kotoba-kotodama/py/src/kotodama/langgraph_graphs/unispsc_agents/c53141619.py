from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MagnetState(TypedDict):
    spec_sheet: dict
    validation_results: List[str]
    is_compliant: bool

def validate_magnet_specs(state: MagnetState):
    specs = state.get('spec_sheet', {})
    results = []
    if specs.get('gauss_strength', 0) < 50:
        results.append('Insufficient magnetic field strength.')
    if not specs.get('safety_certification', False):
        results.append('Missing required safety certification.')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def route_by_compliance(state: MagnetState):
    return 'compliant' if state['is_compliant'] else 'reject'

graph = StateGraph(MagnetState)
graph.add_node('validate', validate_magnet_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_compliance, {'compliant': END, 'reject': END})
graph = graph.compile()
