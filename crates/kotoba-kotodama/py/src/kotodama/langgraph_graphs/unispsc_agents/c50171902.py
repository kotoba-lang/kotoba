from typing import TypedDict
from langgraph.graph import StateGraph, END

class RelishProcurementState(TypedDict):
    quality_passed: bool
    expiry_check: bool
    compliant: bool

def check_quality_standards(state: RelishProcurementState):
    state['quality_passed'] = True
    return state

def verify_shelf_life(state: RelishProcurementState):
    state['expiry_check'] = True
    return state

def finalize_order(state: RelishProcurementState):
    state['compliant'] = state['quality_passed'] and state['expiry_check']
    return state

graph = StateGraph(RelishProcurementState)
graph.add_node("quality_check", check_quality_standards)
graph.add_node("expiry_check", verify_shelf_life)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("quality_check")
graph.add_edge("quality_check", "expiry_check")
graph.add_edge("expiry_check", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
