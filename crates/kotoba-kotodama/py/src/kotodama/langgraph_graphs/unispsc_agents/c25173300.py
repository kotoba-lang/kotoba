from typing import TypedDict
from langgraph.graph import StateGraph, END

class ControlSystemState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_specs(state: ControlSystemState):
    specs = state.get('spec_data', {})
    checks = ['protocol' in specs, 'redundancy' in specs]
    return {'validation_results': checks, 'is_compliant': all(checks)}

def finalize_procurement(state: ControlSystemState): return {'is_compliant': state['is_compliant']}

graph = StateGraph(ControlSystemState)
graph.add_node('validate', validate_specs)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
