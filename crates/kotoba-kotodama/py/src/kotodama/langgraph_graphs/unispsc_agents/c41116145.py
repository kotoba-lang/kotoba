from typing import TypedDict
from langgraph.graph import StateGraph, END

class VirologyState(TypedDict):
    lot_id: str
    compliance_checked: bool
    temp_log_verified: bool

def validate_lot(state: VirologyState):
    state['compliance_checked'] = bool(state.get('lot_id'))
    return state

def verify_cold_chain(state: VirologyState):
    state['temp_log_verified'] = True
    return state

graph = StateGraph(VirologyState)
graph.add_node("validate", validate_lot)
graph.add_node("cold_chain", verify_cold_chain)
graph.add_edge("validate", "cold_chain")
graph.add_edge("cold_chain", END)
graph.set_entry_point("validate")
graph = graph.compile()
