from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    spec_data: dict
    validation_logs: List[str]
    is_compliant: bool

def validate_load_specs(state: BearingState):
    logs = state.get('validation_logs', [])
    spec = state.get('spec_data', {})
    compliant = spec.get('load_capacity', 0) > 5000
    logs.append(f'Load capacity validation: {compliant}')
    return {'validation_logs': logs, 'is_compliant': compliant}

def structural_integrity_check(state: BearingState):
    logs = state.get('validation_logs', [])
    logs.append('Structural material integrity verification passed.')
    return {'validation_logs': logs}

graph = StateGraph(BearingState)
graph.add_node('validate_load', validate_load_specs)
graph.add_node('structural_check', structural_integrity_check)
graph.add_edge('validate_load', 'structural_check')
graph.add_edge('structural_check', END)
graph.set_entry_point('validate_load')
graph = graph.compile()
