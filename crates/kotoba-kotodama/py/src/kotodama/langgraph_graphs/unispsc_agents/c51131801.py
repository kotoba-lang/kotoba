from typing import TypedDict
from langgraph.graph import StateGraph, END

class FibrinogenState(TypedDict):
    purity: float
    temp_log: list
    is_compliant: bool

def validate_cold_chain(state: FibrinogenState):
    # Business logic for monitoring transport temperatures
    state['is_compliant'] = all(t < 8.0 for t in state.get('temp_log', [0]))
    return state

def check_purity(state: FibrinogenState):
    state['is_compliant'] = state['is_compliant'] and (state.get('purity', 0) > 95.0)
    return state

graph = StateGraph(FibrinogenState)
graph.add_node('validate_temp', validate_cold_chain)
graph.add_node('validate_purity', check_purity)
graph.set_entry_point('validate_temp')
graph.add_edge('validate_temp', 'validate_purity')
graph.add_edge('validate_purity', END)
graph = graph.compile()
