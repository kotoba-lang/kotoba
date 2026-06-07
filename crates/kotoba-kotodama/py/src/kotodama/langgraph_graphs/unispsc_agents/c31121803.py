from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    material_certified: bool
    dimensional_check_passed: bool
    final_approval: bool

def validate_specs(state: CastingState):
    state['material_certified'] = True
    return state

def run_dimensional_audit(state: CastingState):
    state['dimensional_check_passed'] = True
    return state

graph = StateGraph(CastingState)
graph.add_node('validation', validate_specs)
graph.add_node('audit', run_dimensional_audit)
graph.add_edge('validation', 'audit')
graph.add_edge('audit', END)
graph.set_entry_point('validation')

graph = graph.compile()
