from typing import TypedDict
from langgraph.graph import StateGraph, END

class CableState(TypedDict):
    spec_data: dict
    validation_log: list
    is_compliant: bool

def validate_cable_specs(state: CableState):
    specs = state.get('spec_data', {})
    log = []
    if 'Tensile strength rating' not in specs:
        log.append('Missing tensile strength requirement')
    return {'validation_log': log, 'is_compliant': len(log) == 0}

graph = StateGraph(CableState)
graph.add_node('validate', validate_cable_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
