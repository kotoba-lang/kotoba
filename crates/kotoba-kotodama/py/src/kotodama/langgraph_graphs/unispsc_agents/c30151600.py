from typing import TypedDict
from langgraph.graph import StateGraph, END

class RoofingState(TypedDict):
    material_spec: str
    compliance_report: str
    validated: bool

def validate_roofing_specs(state: RoofingState):
    # Simulate CAD compliance validation logic for roofing geometry
    state['validated'] = len(state.get('material_spec', '')) > 10
    state['compliance_report'] = 'Compliance Verified' if state['validated'] else 'Invalid Specs'
    return state

graph = StateGraph(RoofingState)
graph.add_node('validate', validate_roofing_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
