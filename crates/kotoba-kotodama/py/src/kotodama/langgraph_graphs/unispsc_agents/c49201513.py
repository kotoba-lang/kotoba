from typing import TypedDict
from langgraph.graph import StateGraph, END

class TrampolineState(TypedDict):
    capacity: float
    safe_cert: bool
    approved: bool

def validate_specs(state: TrampolineState):
    is_safe = state.get('capacity', 0) > 0 and state.get('safe_cert', False)
    return {'approved': is_safe}

graph = StateGraph(TrampolineState)
graph.add_node('validation', validate_specs)
graph.set_entry_point('validation')
graph.add_edge('validation', END)
graph = graph.compile()
