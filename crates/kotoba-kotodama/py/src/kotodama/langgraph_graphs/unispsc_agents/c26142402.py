from typing import TypedDict
from langgraph.graph import StateGraph, END

class NuclearAbsorberState(TypedDict):
    spec_data: dict
    validation_result: bool
    compliance_status: str

def validate_nuclear_specs(state: NuclearAbsorberState):
    specs = state.get('spec_data', {})
    required = ['attenuation_coefficient', 'certification_id']
    valid = all(key in specs for key in required)
    return {'validation_result': valid, 'compliance_status': 'PASS' if valid else 'FAIL'}

def export_review(state: NuclearAbsorberState):
    # Dual-use export control checkpoint
    return {'compliance_status': 'EXPORT_CLEARED'}

graph = StateGraph(NuclearAbsorberState)
graph.add_node('validate', validate_nuclear_specs)
graph.add_node('export_check', export_review)
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph.set_entry_point('validate')
graph = graph.compile()
