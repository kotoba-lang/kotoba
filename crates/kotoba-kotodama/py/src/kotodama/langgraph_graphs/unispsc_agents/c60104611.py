from typing import TypedDict
from langgraph.graph import StateGraph, END

class AppState(TypedDict):
    spec: dict
    validated: bool

def validate_apparatus(state: AppState):
    cert = state.get('spec', {}).get('certification')
    pressure = state.get('spec', {}).get('pressure_rating', 0)
    state['validated'] = bool(cert and pressure > 0)
    return state

graph = StateGraph(AppState)
graph.add_node('validate', validate_apparatus)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
