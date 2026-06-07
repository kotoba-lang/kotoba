from typing import TypedDict
from langgraph.graph import StateGraph, END

class FoodProcurementState(TypedDict):
    product_name: str
    quality_check_passed: bool
    compliance_docs: list

def validate_safety(state: FoodProcurementState):
    state['quality_check_passed'] = True
    return state

def verify_compliance(state: FoodProcurementState):
    state['compliance_docs'] = ['ISO_22000', 'Phytosanitary_Cert']
    return state

graph = StateGraph(FoodProcurementState)
graph.add_node('safety_check', validate_safety)
graph.add_node('compliance_check', verify_compliance)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
