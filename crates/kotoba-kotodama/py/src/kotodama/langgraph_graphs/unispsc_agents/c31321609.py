from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    part_id: str
    welding_params: dict
    validation_passed: bool
    error_logs: List[str]

def validate_specs(state: AssemblyState) -> AssemblyState:
    params = state.get('welding_params', {})
    state['validation_passed'] = params.get('pressure', 0) > 0 and params.get('frequency', 0) > 20000
    return state

def route_quality(state: AssemblyState) -> str:
    return 'passed' if state['validation_passed'] else 'failed'

graph = StateGraph(AssemblyState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_quality, {'passed': END, 'failed': END})
graph = graph.compile()
