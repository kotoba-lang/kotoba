from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class DairyState(TypedDict):
    product_id: str
    temp_log: List[float]
    is_compliant: bool

def validate_cold_chain(state: DairyState):
    state['is_compliant'] = all(t < 5.0 for t in state.get('temp_log', []))
    return state

def check_expiry(state: DairyState):
    return state

graph = StateGraph(DairyState)
graph.add_node('validate_temp', validate_cold_chain)
graph.add_node('check_expiry', check_expiry)
graph.set_entry_point('validate_temp')
graph.add_edge('validate_temp', 'check_expiry')
graph.add_edge('check_expiry', END)
graph = graph.compile()
