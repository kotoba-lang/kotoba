from langgraph.graph import StateGraph, END
from typing import TypedDict

class OphthalmicState(TypedDict):
    spec_data: dict
    validated: bool
    compliance_report: str

def validate_medical_grade(state: OphthalmicState):
    material = state.get('spec_data', {}).get('material', '')
    is_valid = material in ['Titanium', 'Stainless Steel 316L']
    return {'validated': is_valid, 'compliance_report': 'Material check passed' if is_valid else 'Non-compliant material'}

def check_certification(state: OphthalmicState):
    cert = state.get('spec_data', {}).get('iso_cert', False)
    return {'validated': cert}

graph = StateGraph(OphthalmicState)
graph.add_node('material_check', validate_medical_grade)
graph.add_node('cert_check', check_certification)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'cert_check')
graph.add_edge('cert_check', END)
graph = graph.compile()
