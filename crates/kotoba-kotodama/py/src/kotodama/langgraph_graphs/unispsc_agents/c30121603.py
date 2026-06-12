from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    material_name: str
    purity_check: bool
    hazard_clearance: bool

def validate_quality(state: State) -> State:
    # Simulate chemical property validation for Gilsonite
    state['purity_check'] = True
    return state

def check_hazmat(state: State) -> State:
    # Simulate dangerous goods compliance workflow
    state['hazard_clearance'] = True
    return state

graph = StateGraph(State)
graph.add_node('quality', validate_quality)
graph.add_node('hazmat', check_hazmat)
graph.set_entry_point('quality')
graph.add_edge('quality', 'hazmat')
graph.add_edge('hazmat', END)
graph = graph.compile()
