from typing import TypedDict
from langgraph.graph import StateGraph, END

class FabricState(TypedDict):
    composition: dict
    test_results: dict
    is_compliant: bool

def validate_specs(state: FabricState):
    composition = state.get('composition', {})
    state['is_compliant'] = composition.get('cotton', 0) > 0 and composition.get('synthetic', 0) > 0
    return state

def run_quality_check(state: FabricState):
    print('Running textile inspection for cotton blends...')
    return {'test_results': {'passed': state['is_compliant']}}

graph = StateGraph(FabricState)
graph.add_node('validate', validate_specs)
graph.add_node('inspection', run_quality_check)
graph.add_edge('validate', 'inspection')
graph.add_edge('inspection', END)
graph.set_entry_point('validate')
graph = graph.compile()
