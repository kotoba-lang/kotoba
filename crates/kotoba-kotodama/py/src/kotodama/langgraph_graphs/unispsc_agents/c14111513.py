from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class TonerProcessState(TypedDict):
    cartridge_id: str
    compatibility_verified: bool
    yield_tested: bool
    status: str

def check_compatibility(state: TonerProcessState) -> TonerProcessState:
    # Simulate OME compatibility verification
    state['compatibility_verified'] = True
    return state

def run_yield_test(state: TonerProcessState) -> TonerProcessState:
    # Simulate page yield quality check
    state['yield_tested'] = True
    return state

def finalize_procurement(state: TonerProcessState) -> TonerProcessState:
    state['status'] = 'COMPLETED'
    return state

graph = StateGraph(TonerProcessState)
graph.add_node('check_comp', check_compatibility)
graph.add_node('yield_test', run_yield_test)
graph.add_node('finalize', finalize_procurement)

graph.set_entry_point('check_comp')
graph.add_edge('check_comp', 'yield_test')
graph.add_edge('yield_test', 'finalize')
graph.add_edge('finalize', END)

graph = graph.compile()
