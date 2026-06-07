from typing import TypedDict
from langgraph.graph import StateGraph, END

class StenotypeState(TypedDict):
    model_id: str
    input_speed: int
    is_validated: bool

def validate_specs(state: StenotypeState):
    state['is_validated'] = state.get('input_speed', 0) >= 200
    return state

graph = StateGraph(StenotypeState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
