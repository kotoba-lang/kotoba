from typing import TypedDict
from langgraph.graph import StateGraph, END

class HematologyProcurementState(TypedDict):
    part_number: str
    expiry_check: bool
    regulatory_compliant: bool
    validation_status: str

def validate_product(state: HematologyProcurementState):
    state['validation_status'] = 'Validating regulatory compliance for hematology reagents'
    state['regulatory_compliant'] = True
    return state

def check_shelf_life(state: HematologyProcurementState):
    state['expiry_check'] = True
    return state

graph = StateGraph(HematologyProcurementState)
graph.add_node('validate', validate_product)
graph.add_node('expiry', check_shelf_life)
graph.set_entry_point('validate')
graph.add_edge('validate', 'expiry')
graph.add_edge('expiry', END)

graph = graph.compile()
