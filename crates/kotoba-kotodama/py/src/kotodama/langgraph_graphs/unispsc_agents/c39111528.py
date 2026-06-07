from typing import TypedDict
from langgraph.graph import StateGraph, END

class LightingState(TypedDict):
    specs: dict
    is_compliant: bool
    error_log: list

def validate_specs(state: LightingState):
    s = state.get('specs', {})
    errors = []
    if s.get('voltage') not in [100, 120, 220]: errors.append('Invalid Voltage')
    if not s.get('certification'): errors.append('Missing Safety Cert')
    return {'is_compliant': len(errors) == 0, 'error_log': errors}

graph = StateGraph(LightingState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
