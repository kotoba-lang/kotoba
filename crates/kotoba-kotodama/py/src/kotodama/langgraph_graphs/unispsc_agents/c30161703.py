from typing import TypedDict
from langgraph.graph import StateGraph, END

class LinoleumState(TypedDict):
    material_spec: dict
    compliance_report: str
    is_approved: bool

def validate_material(state: LinoleumState):
    spec = state.get('material_spec', {})
    is_compliant = spec.get('fire_resistant') and spec.get('eco_certified')
    return {'is_approved': is_compliant, 'compliance_report': 'Validated against ISO 24011' if is_compliant else 'Failed: Missing certifications'}

graph = StateGraph(LinoleumState)
graph.add_node('validation', validate_material)
graph.set_entry_point('validation')
graph.add_edge('validation', END)
graph = graph.compile()
