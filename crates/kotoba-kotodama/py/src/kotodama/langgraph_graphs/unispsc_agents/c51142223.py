from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    api_code: str
    compliance_cleared: bool
    shipping_validated: bool

def validate_controlled_substance(state: ProcurementState):
    print('Checking regulatory license for Hydrocodone...')
    return {'compliance_cleared': True}

def check_cold_chain(state: ProcurementState):
    print('Validating storage temperature requirements...')
    return {'shipping_validated': True}

graph = StateGraph(ProcurementState)
graph.add_node('regulatory_check', validate_controlled_substance)
graph.add_node('shipping_check', check_cold_chain)
graph.set_entry_point('regulatory_check')
graph.add_edge('regulatory_check', 'shipping_check')
graph.add_edge('shipping_check', END)
graph = graph.compile()
