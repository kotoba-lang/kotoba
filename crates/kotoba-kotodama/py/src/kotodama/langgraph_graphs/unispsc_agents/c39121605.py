from typing import TypedDict
from langgraph.graph import StateGraph, END

class FuseState(TypedDict):
    specs: dict
    is_compliant: bool

def validate_fuse_specs(state: FuseState) -> FuseState:
    specs = state.get('specs', {})
    required = ['rated_voltage', 'rated_current']
    state['is_compliant'] = all(k in specs for k in required)
    return state

graph = StateGraph(FuseState)
graph.add_node('validate', validate_fuse_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
