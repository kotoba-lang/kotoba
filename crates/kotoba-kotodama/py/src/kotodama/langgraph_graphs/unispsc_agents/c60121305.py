from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class CutterState(TypedDict):
    blade_spec: str
    blade_size: float
    has_safety_guard: bool
    compliance_checked: bool

def validate_specs(state: CutterState) -> CutterState:
    if not state.get('has_safety_guard'):
        raise ValueError('Safety guard is mandatory for procurement')
    state['compliance_checked'] = True
    return state

graph = StateGraph(CutterState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
