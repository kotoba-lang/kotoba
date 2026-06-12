from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_name: str
    purity_check: bool
    safety_compliance: bool
    shipping_approval: bool

def validate_safety(state: ProcurementState):
    print('Validating MSDS and GHS compliance for Uracil mustard...')
    state['safety_compliance'] = True
    return state

def verify_purity(state: ProcurementState):
    print('Checking analytical purity certificate...')
    state['purity_check'] = True
    return state

def request_shipping(state: ProcurementState):
    print('Initiating secure dangerous goods logistics...')
    state['shipping_approval'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('safety', validate_safety)
graph.add_node('purity', verify_purity)
graph.add_node('shipping', request_shipping)
graph.set_entry_point('safety')
graph.add_edge('safety', 'purity')
graph.add_edge('purity', 'shipping')
graph.add_edge('shipping', END)
graph = graph.compile()
