from typing import TypedDict
from langgraph.graph import StateGraph, END

class ConnectorState(TypedDict):
    specs: dict
    validated: bool
    error_log: list

def validate_specs(state: ConnectorState):
    specs = state.get('specs', {})
    req_keys = ['Voltage Rating', 'Conductor Gauge Range']
    valid = all(k in specs for k in req_keys)
    return {'validated': valid, 'error_log': [] if valid else ['Missing specs']}

def finalize_procurement(state: ConnectorState):
    return {'validated': True}

graph = StateGraph(ConnectorState)
graph.add_node('validator', validate_specs)
graph.add_node('finalizer', finalize_procurement)
graph.set_entry_point('validator')
graph.add_edge('validator', 'finalizer')
graph.add_edge('finalizer', END)
graph = graph.compile()
