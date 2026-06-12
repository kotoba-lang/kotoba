from typing import TypedDict
from langgraph.graph import StateGraph, END

class InstrumentState(TypedDict):
    model: str
    quality_check_passed: bool
    is_verified: bool

def validate_trombone_specs(state: InstrumentState):
    state['quality_check_passed'] = bool(state.get('model'))
    return state

def formal_verification(state: InstrumentState):
    state['is_verified'] = state['quality_check_passed']
    return state

graph = StateGraph(InstrumentState)
graph.add_node('validate', validate_trombone_specs)
graph.add_node('verify', formal_verification)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()
