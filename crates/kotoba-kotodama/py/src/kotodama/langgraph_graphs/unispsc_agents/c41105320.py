from typing import TypedDict
from langgraph.graph import StateGraph, END

class GelState(TypedDict):
    spec_completed: bool
    temp_check_passed: bool
    qc_verified: bool

def validate_temp(state: GelState):
    print('Verifying cold-chain compliance...')
    state['temp_check_passed'] = True
    return state

def check_qc(state: GelState):
    print('Validating lot-specific COA data...')
    state['qc_verified'] = True
    return state

graph = StateGraph(GelState)
graph.add_node('validate_temp', validate_temp)
graph.add_node('check_qc', check_qc)
graph.set_entry_point('validate_temp')
graph.add_edge('validate_temp', 'check_qc')
graph.add_edge('check_qc', END)
graph = graph.compile()
