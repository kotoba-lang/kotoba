from typing import TypedDict
from langgraph.graph import StateGraph, END

class BosentanState(TypedDict):
    purity: float
    storage_temp: float
    gmp_valid: bool
    approved: bool

def validate_quality(state: BosentanState):
    return {'approved': state.get('purity', 0) >= 99.0 and state.get('gmp_valid', False)}

def check_cold_chain(state: BosentanState):
    temp = state.get('storage_temp', 25.0)
    return {'approved': state.get('approved', False) and 15.0 <= temp <= 25.0}

graph = StateGraph(BosentanState)
graph.add_node('validate', validate_quality)
graph.add_node('cold_chain', check_cold_chain)
graph.set_entry_point('validate')
graph.add_edge('validate', 'cold_chain')
graph.add_edge('cold_chain', END)
graph = graph.compile()
