from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MicroscopeState(TypedDict):
    part_number: str
    optical_spec: dict
    is_compliant: bool
    validation_log: List[str]

def validate_optics(state: MicroscopeState):
    log = state.get('validation_log', [])
    spec = state.get('optical_spec', {})
    compliant = spec.get('coating_type') is not None and spec.get('tolerance') < 0.05
    log.append('Optical validation pass' if compliant else 'Optical validation fail')
    return {'is_compliant': compliant, 'validation_log': log}

graph = StateGraph(MicroscopeState)
graph.add_node('validate', validate_optics)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
