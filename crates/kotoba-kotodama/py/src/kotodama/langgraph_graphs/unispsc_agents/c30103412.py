from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class IngotsState(TypedDict):
    material_spec: str
    composition_data: dict
    approved: bool

def validate_composition(state: IngotsState):
    # Business logic for non-ferrous alloy chemical validation
    comp = state.get('composition_data', {})
    state['approved'] = all(val > 0 for val in comp.values())
    return state

def check_compliance(state: IngotsState):
    # Check metallurgical standards
    return 'approved' if state['approved'] else 'rejected'

graph = StateGraph(IngotsState)
graph.add_node('validate', validate_composition)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
