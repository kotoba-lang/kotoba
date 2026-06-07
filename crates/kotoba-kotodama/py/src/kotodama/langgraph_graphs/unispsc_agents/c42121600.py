from typing import TypedDict
from langgraph.graph import StateGraph, END

class VetProductState(TypedDict):
    product_id: str
    compliance_ok: bool
    temp_control: bool

def validate_compliance(state: VetProductState) -> VetProductState:
    state['compliance_ok'] = True
    return state

def check_cold_chain(state: VetProductState) -> VetProductState:
    state['temp_control'] = True
    return state

graph = StateGraph(VetProductState)
graph.add_node('compliance', validate_compliance)
graph.add_node('storage', check_cold_chain)
graph.add_edge('compliance', 'storage')
graph.add_edge('storage', END)
graph.set_entry_point('compliance')
graph = graph.compile()
