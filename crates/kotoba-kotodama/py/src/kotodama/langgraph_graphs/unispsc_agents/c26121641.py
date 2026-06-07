from typing import TypedDict
from langgraph.graph import StateGraph, END

class CableState(TypedDict):
    cable_spec: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: CableState):
    log = []
    compliant = True
    spec = state.get('cable_spec', {})
    if 'voltage_class' not in spec:
        log.append('Missing voltage classification')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def route_verification(state: CableState):
    return 'APPROVED' if state['is_compliant'] else 'REJECTED'

graph = StateGraph(CableState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
