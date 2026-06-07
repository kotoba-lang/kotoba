from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalState(TypedDict):
    spec_data: dict
    validation_passed: bool
    compliance_status: str

def validate_materials(state: SurgicalState):
    material = state.get('spec_data', {}).get('material', '')
    return {'validation_passed': material == 'Medical Grade Stainless Steel'}

def check_compliance(state: SurgicalState):
    compliance = state.get('spec_data', {}).get('iso_cert', False)
    return {'compliance_status': 'Compliant' if compliance else 'Non-Compliant'}

graph = StateGraph(SurgicalState)
graph.add_node('material_check', validate_materials)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
