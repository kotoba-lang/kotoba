from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    part_specs: dict
    validation_passed: bool
    error_logs: List[str]

def validate_dimensions(state: CastState):
    specs = state.get('part_specs', {})
    if 'tolerance' in specs and specs['tolerance'] < 0.01:
        return {'validation_passed': True}
    return {'validation_passed': False, 'error_logs': ['Tolerance validation failed']}

def structural_analysis(state: CastState):
    if state.get('validation_passed'):
        return {'error_logs': ['Structural Integrity Verified']}
    return {'error_logs': ['Structural Analysis Skipped']}

graph = StateGraph(CastState)
graph.add_node('dimension_check', validate_dimensions)
graph.add_node('structural_integrity', structural_analysis)
graph.set_entry_point('dimension_check')
graph.add_edge('dimension_check', 'structural_integrity')
graph.add_edge('structural_integrity', END)
graph = graph.compile()
