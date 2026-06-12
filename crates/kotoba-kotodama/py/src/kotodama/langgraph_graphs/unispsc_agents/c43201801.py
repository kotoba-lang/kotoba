from typing import TypedDict
from langgraph.graph import StateGraph, END

class FDDState(TypedDict):
    part_number: str
    is_compatible: bool
    validation_report: str

def validate_fdd(state: FDDState):
    # Simulate CAD/Spec validation for legacy hardware
    state['is_compatible'] = state.get('part_number', '').startswith('FDD')
    state['validation_report'] = 'Validated' if state['is_compatible'] else 'Incompatible legacy part'
    return state

graph = StateGraph(FDDState)
graph.add_node('validate', validate_fdd)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
