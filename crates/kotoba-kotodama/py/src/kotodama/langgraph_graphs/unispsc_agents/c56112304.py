from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ChairSeatState(TypedDict):
    part_id: str
    compatibility_check: bool
    safety_standards_met: bool

def validate_part(state: ChairSeatState) -> ChairSeatState:
    # Simulate CAD/Spec validation logic
    state['compatibility_check'] = state.get('part_id', '').startswith('CS-')
    state['safety_standards_met'] = True
    return state

graph = StateGraph(ChairSeatState)
graph.add_node('validation', validate_part)
graph.set_entry_point('validation')
graph.add_edge('validation', END)
graph = graph.compile()
