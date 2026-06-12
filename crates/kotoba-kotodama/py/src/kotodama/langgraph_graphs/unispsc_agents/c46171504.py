from typing import TypedDict
from langgraph.graph import StateGraph, END

class LockState(TypedDict):
    model_id: str
    security_compliance: bool
    validation_error: str

def validate_specs(state: LockState):
    if not state.get('model_id'): return {'validation_error': 'Missing Model ID'}
    return {'security_compliance': True, 'validation_error': None}

graph = StateGraph(LockState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
