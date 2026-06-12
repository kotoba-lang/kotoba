from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class OvenSpecState(TypedDict):
    voltage: str
    capacity: float
    has_safety_cert: bool
    validation_log: List[str]

def validate_specs(state: OvenSpecState):
    log = []
    if not state.get('has_safety_cert'):
        log.append('Error: Safety certification missing')
    return {'validation_log': log}

graph = StateGraph(OvenSpecState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
