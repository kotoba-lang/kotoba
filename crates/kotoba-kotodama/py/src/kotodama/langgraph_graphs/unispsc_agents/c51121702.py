from typing import TypedDict
from langgraph.graph import StateGraph, END

class PharmState(TypedDict):
    batch_id: str
    purity_validated: bool
    compliant: bool

def validate_pharm_specs(state: PharmState):
    # Simulate chemical validation logic for Terazosin
    state['purity_validated'] = True
    return {'purity_validated': True}

def check_compliance(state: PharmState):
    # Simulate regulatory audit check
    state['compliant'] = state.get('purity_validated', False)
    return {'compliant': True}

graph = StateGraph(PharmState)
graph.add_node('validate', validate_pharm_specs)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
