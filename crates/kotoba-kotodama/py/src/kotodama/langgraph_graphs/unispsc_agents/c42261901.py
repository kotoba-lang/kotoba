from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_type: str
    quality_status: bool
    compliance_check: bool

def validate_material(state: ProcurementState):
    print('Validating forensic-grade material properties...')
    return {'quality_status': True}

def check_compliance(state: ProcurementState):
    print('Checking regulatory compliance for forensic equipment...')
    return {'compliance_check': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_material)
graph.add_node('compliance', check_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
