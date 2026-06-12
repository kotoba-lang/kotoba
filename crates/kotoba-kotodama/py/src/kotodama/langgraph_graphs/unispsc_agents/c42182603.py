from typing import TypedDict
from langgraph.graph import StateGraph, END

class MedicalLightState(TypedDict):
    spec_sheet: dict
    approved: bool

def validate_specs(state: MedicalLightState):
    specs = state.get('spec_sheet', {})
    is_compliant = specs.get('luminance', 0) > 20000 and specs.get('iso_cert', False)
    return {'approved': is_compliant}

def route_by_approval(state: MedicalLightState):
    return 'approved' if state['approved'] else 'rejected'

graph = StateGraph(MedicalLightState)
graph.add_node('validation', validate_specs)
graph.add_edge('validation', END)
graph.set_entry_point('validation')

graph = graph.compile()
