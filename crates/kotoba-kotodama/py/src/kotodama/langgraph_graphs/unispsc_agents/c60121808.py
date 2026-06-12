from typing import TypedDict
from langgraph.graph import StateGraph, END

class InkProcessingState(TypedDict):
    ink_type: str
    viscosity_check: bool
    sds_verified: bool
    approved: bool

def check_sds(state: InkProcessingState):
    # Simulate verification logic
    state['sds_verified'] = True
    return state

def validate_quality(state: InkProcessingState):
    # Simulate quality control
    state['viscosity_check'] = True
    state['approved'] = state['sds_verified'] and state['viscosity_check']
    return state

graph = StateGraph(InkProcessingState)
graph.add_node('verify_sds', check_sds)
graph.add_node('qc_check', validate_quality)
graph.set_entry_point('verify_sds')
graph.add_edge('verify_sds', 'qc_check')
graph.add_edge('qc_check', END)
graph = graph.compile()
