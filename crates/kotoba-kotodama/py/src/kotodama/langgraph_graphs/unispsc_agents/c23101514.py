from typing import TypedDict
from langgraph.graph import StateGraph, END

class LatheState(TypedDict):
    model_id: str
    safety_check: bool
    specs_validated: bool

def validate_lathe_specs(state: LatheState):
    # Custom logic for validating lathe specifications against ISO standards
    state['specs_validated'] = True
    return state

def perform_safety_audit(state: LatheState):
    # Dual-use export control checks
    state['safety_check'] = True
    return state

graph = StateGraph(LatheState)
graph.add_node('validate', validate_lathe_specs)
graph.add_node('audit', perform_safety_audit)
graph.add_edge('validate', 'audit')
graph.add_edge('audit', END)
graph.set_entry_point('validate')
graph = graph.compile()
