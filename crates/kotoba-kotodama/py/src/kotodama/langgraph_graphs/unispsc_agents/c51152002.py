from typing import TypedDict
from langgraph.graph import StateGraph, END

class MivacuriumState(TypedDict):
    batch_number: str
    purity_validated: bool
    temp_log_compliant: bool
    ready_for_dispatch: bool

def validate_batch(state: MivacuriumState):
    return {"purity_validated": True}

def check_cold_chain(state: MivacuriumState):
    return {"temp_log_compliant": True}

def finalize_order(state: MivacuriumState):
    return {"ready_for_dispatch": True}

graph = StateGraph(MivacuriumState)
graph.add_node("validate", validate_batch)
graph.add_node("cold_chain", check_cold_chain)
graph.add_node("finalize", finalize_order)
graph.set_entry_point("validate")
graph.add_edge("validate", "cold_chain")
graph.add_edge("cold_chain", "finalize")
graph.add_edge("finalize", END)
graph = graph.compile()
