from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class TrailerState(TypedDict):
    temp_range: str
    atp_compliant: bool
    telemetry_enabled: bool
    validation_errors: List[str]

def validate_specs(state: TrailerState):
    errors = []
    if not state.get('atp_compliant'):
        errors.append('Missing ATP certification')
    return {'validation_errors': errors}

def route_logic(state: TrailerState):
    return 'END' if not state['validation_errors'] else 'END'

graph = StateGraph(TrailerState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
