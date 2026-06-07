from langgraph.graph import StateGraph, END
from typing import TypedDict

class OpticalState(TypedDict):
    spec_data: dict
    is_compliant: bool

def validate_optics(state: OpticalState):
    threshold = state.get('spec_data', {}).get('laser_damage_threshold', 0)
    state['is_compliant'] = threshold > 5.0
    return state

def export_review(state: OpticalState):
    # Dual-use compliance check logic
    return state

graph = StateGraph(OpticalState)
graph.add_node('validate', validate_optics)
graph.add_node('export_check', export_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
