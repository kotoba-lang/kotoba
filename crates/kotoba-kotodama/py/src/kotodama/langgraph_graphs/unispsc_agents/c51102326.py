from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    api_name: str
    purity_cert: bool
    gmp_verified: bool

def validate_quality(state: ProcurementState):
    print('Validating Efavirenz quality standards...')
    return {'purity_cert': True}

def check_compliance(state: ProcurementState):
    print('Checking GMP compliance for API...')
    return {'gmp_verified': True}

graph = StateGraph(ProcurementState)
graph.add_node('quality_check', validate_quality)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('quality_check')
graph.add_edge('quality_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
