from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    purity_level: float
    requires_cold_chain: bool
    is_compliant: bool

def validate_chemical_specs(state: ProcurementState):
    purity = state.get('purity_level', 0)
    state['is_compliant'] = purity >= 99.0
    return state

def check_storage_logistics(state: ProcurementState):
    state['requires_cold_chain'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_chemical_specs)
graph.add_node('logistics', check_storage_logistics)
graph.add_edge('validate', 'logistics')
graph.add_edge('logistics', END)
graph.set_entry_point('validate')
graph = graph.compile()
