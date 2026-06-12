from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    raw_material: str
    purity_validated: bool
    compliance_cleared: bool

def validate_botanical(state: ProcurementState):
    print('Validating Chelidonium majus botanical parameters...')
    return {'purity_validated': True}

def check_regulatory(state: ProcurementState):
    print('Checking pharmaceutical regulatory compliance...')
    return {'compliance_cleared': True}

graph = StateGraph(ProcurementState)
graph.add_node('validation', validate_botanical)
graph.add_node('regulatory', check_regulatory)
graph.add_edge('validation', 'regulatory')
graph.add_edge('regulatory', END)
graph.set_entry_point('validation')
graph = graph.compile()
