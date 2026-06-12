from typing import TypedDict, Annotated, Sequence
from langgraph.graph import StateGraph, END
import operator

class PolymerState(TypedDict):
    batch_id: str
    spec_requirements: dict
    analysis_results: dict
    is_compliant: bool

def validate_batch_purity(state: PolymerState):
    purity = state.get('analysis_results', {}).get('purity_percentage', 0)
    req = state.get('spec_requirements', {}).get('purity_percentage', 99.0)
    return {'is_compliant': purity >= req}

def route_verification(state: PolymerState):
    return 'compliant' if state['is_compliant'] else 'flag_manual'

graph = StateGraph(PolymerState)
graph.add_node('validate', validate_batch_purity)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_verification, {'compliant': END, 'flag_manual': END})
graph = graph.compile()
