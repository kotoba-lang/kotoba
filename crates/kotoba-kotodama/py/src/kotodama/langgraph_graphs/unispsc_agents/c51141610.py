from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChemicalProcurementState(TypedDict):
    purity: float
    cas_valid: bool
    safety_clearance: bool

def validate_purity(state: ChemicalProcurementState):
    state['purity'] = 99.9 if state.get('purity', 0) >= 99.9 else 0.0
    return state

def check_compliance(state: ChemicalProcurementState):
    state['cas_valid'] = True
    state['safety_clearance'] = state.get('purity') > 99
    return state

graph = StateGraph(ChemicalProcurementState)
graph.add_node('validate', validate_purity)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
