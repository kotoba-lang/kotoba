from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class KitState(TypedDict):
    kit_id: str
    cold_chain_validation: bool
    qc_data: List[str]

def validate_cold_chain(state: KitState):
    state['cold_chain_validation'] = True
    return state

def run_qc_check(state: KitState):
    state['qc_data'] = ['Transformation Efficiency Verified', 'Sterility Confirmed']
    return state

graph = StateGraph(KitState)
graph.add_node('validate_cold_chain', validate_cold_chain)
graph.add_node('qc_check', run_qc_check)
graph.add_edge('validate_cold_chain', 'qc_check')
graph.add_edge('qc_check', END)
graph.set_entry_point('validate_cold_chain')
graph = graph.compile()
