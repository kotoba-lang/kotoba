from typing import TypedDict
from langgraph.graph import StateGraph, END

class CentrifugeState(TypedDict):
    adapter_spec: dict
    validation_status: bool

def validate_adapter(state: CentrifugeState):
    spec = state.get('adapter_spec', {})
    # Logic to ensure max_g matches centrifuge speed requirements
    is_valid = spec.get('max_g', 0) >= spec.get('required_g', 0)
    return {'validation_status': is_valid}

def route_by_spec(state: CentrifugeState):
    return 'validate' if state.get('validation_status', False) is False else END

graph = StateGraph(CentrifugeState)
graph.add_node('validate', validate_adapter)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
