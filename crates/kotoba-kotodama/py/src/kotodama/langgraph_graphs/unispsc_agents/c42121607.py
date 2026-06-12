from typing import TypedDict
from langgraph.graph import StateGraph, END

class VetMedState(TypedDict):
    product_id: str
    compliance_check: bool
    temp_log_verified: bool

def validate_product(state: VetMedState):
    print('Validating veterinary drug compliance...')
    return {'compliance_check': True}

def verify_storage(state: VetMedState):
    print('Verifying temperature control logs...')
    return {'temp_log_verified': True}

graph = StateGraph(VetMedState)
graph.add_node('validate', validate_product)
graph.add_node('storage', verify_storage)
graph.set_entry_point('validate')
graph.add_edge('validate', 'storage')
graph.add_edge('storage', END)
graph = graph.compile()
