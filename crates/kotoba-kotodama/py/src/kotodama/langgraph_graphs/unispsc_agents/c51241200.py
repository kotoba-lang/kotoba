from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class MedState(TypedDict):
    product_sku: str
    compliance_docs: List[str]
    temp_control_verified: bool

def validate_compliance(state: MedState):
    print(f'Validating GMP for {state[product_sku]}')
    return {'compliance_docs': ['verified_gmp']}

def check_cold_chain(state: MedState):
    print('Verifying temperature logging requirements')
    return {'temp_control_verified': True}

graph = StateGraph(MedState)
graph.add_node('compliance', validate_compliance)
graph.add_node('logistics', check_cold_chain)
graph.set_entry_point('compliance')
graph.add_edge('compliance', 'logistics')
graph.add_edge('logistics', END)
graph = graph.compile()
