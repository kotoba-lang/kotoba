from typing import TypedDict
from langgraph.graph import StateGraph, END

class LabQCState(TypedDict):
    product_name: str
    batch_number: str
    stability_data: dict
    is_compliant: bool

def validate_stability(state: LabQCState):
    temp = state.get('stability_data', {}).get('temp', 0)
    state['is_compliant'] = temp <= -20
    return state

def check_traceability(state: LabQCState):
    return state

graph = StateGraph(LabQCState)
graph.add_node("validate", validate_stability)
graph.add_node("traceability", check_traceability)
graph.add_edge("validate", "traceability")
graph.add_edge("traceability", END)
graph.set_entry_point("validate")
graph = graph.compile()
