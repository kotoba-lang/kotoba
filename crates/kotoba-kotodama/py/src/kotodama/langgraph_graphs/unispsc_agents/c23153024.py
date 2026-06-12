from langgraph.graph import StateGraph, END
from typing import TypedDict, List
class LaserState(TypedDict):
    power_rating: int
    safety_compliance: bool
    export_control_check: bool

def validate_safety(state: LaserState):
    state['safety_compliance'] = state.get('power_rating', 0) > 0
    return state

def check_export_controls(state: LaserState):
    state['export_control_check'] = True
    return state

graph = StateGraph(LaserState)
graph.add_node('safety', validate_safety)
graph.add_node('export', check_export_controls)
graph.add_edge('safety', 'export')
graph.add_edge('export', END)
graph.set_entry_point('safety')
graph = graph.compile()
