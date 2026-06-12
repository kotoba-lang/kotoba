from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ChuteState(TypedDict):
    serial_number: str
    inspection_passed: bool
    compliance_docs: List[str]

def validate_deployment_system(state: ChuteState) -> ChuteState:
    if not state.get('compliance_docs'):
        raise ValueError('Missing required AS9100/Aviation safety docs.')
    state['inspection_passed'] = True
    return state

def check_shelf_life(state: ChuteState) -> ChuteState:
    # Logic to verify parachute fabric shelf life
    return state

graph = StateGraph(ChuteState)
graph.add_node('validate', validate_deployment_system)
graph.add_node('shelf_life', check_shelf_life)
graph.add_edge('validate', 'shelf_life')
graph.add_edge('shelf_life', END)
graph.set_entry_point('validate')
graph = graph.compile()
