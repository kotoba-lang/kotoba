from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_id: str
    compliance_checked: bool
    expiry_check: bool

def validate_compliance(state: ProcurementState):
    print('Validating GMP and ingredient compliance records...')
    return {'compliance_checked': True}

def validate_storage(state: ProcurementState):
    print('Ensuring shelf-life and temperature controls are feasible...')
    return {'expiry_check': True}

graph = StateGraph(ProcurementState)
graph.add_node('compliance', validate_compliance)
graph.add_node('storage', validate_storage)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'storage')
graph.add_edge('storage', END)
graph = graph.compile()
