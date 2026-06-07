from typing import TypedDict, Annotated
from langgraph.graph import StateGraph, END

class BreedingState(TypedDict):
    material_id: str
    quality_passed: bool
    temp_log_verified: bool
    quarantine_cleared: bool

def validate_temp(state: BreedingState) -> BreedingState:
    state['temp_log_verified'] = True
    return state

def check_health(state: BreedingState) -> BreedingState:
    state['quarantine_cleared'] = True
    return state

def finalize_order(state: BreedingState) -> BreedingState:
    state['quality_passed'] = state['temp_log_verified'] and state['quarantine_cleared']
    return state

graph = StateGraph(BreedingState)
graph.add_node('verify_temp', validate_temp)
graph.add_node('health_check', check_health)
graph.add_node('finalizer', finalize_order)
graph.set_entry_point('verify_temp')
graph.add_edge('verify_temp', 'health_check')
graph.add_edge('health_check', 'finalizer')
graph.add_edge('finalizer', END)
graph = graph.compile()
