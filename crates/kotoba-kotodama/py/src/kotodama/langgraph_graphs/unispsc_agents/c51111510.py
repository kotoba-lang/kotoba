from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    product_name: str
    is_hazardous: bool
    compliance_certified: bool

def validate_hazardous_material(state: ProcurementState):
    state['is_hazardous'] = True
    return state

def check_certification(state: ProcurementState):
    state['compliance_certified'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_hazardous_material)
graph.add_node('certify', check_certification)
graph.add_edge('validate', 'certify')
graph.add_edge('certify', END)
graph.set_entry_point('validate')
graph = graph.compile()
