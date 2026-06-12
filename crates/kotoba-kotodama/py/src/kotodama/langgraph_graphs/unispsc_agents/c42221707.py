from typing import TypedDict
from langgraph.graph import StateGraph, END

class InfusionState(TypedDict):
    spec_data: dict
    compliance_score: float
    status: str

def validate_medical_specs(state: InfusionState):
    specs = state.get('spec_data', {})
    if 'sterilization_method' in specs and 'biocompatibility_certification' in specs:
        return {'compliance_score': 1.0, 'status': 'PASS'}
    return {'compliance_score': 0.0, 'status': 'FAIL'}

def finalize_procurement(state: InfusionState):
    return {'status': 'READY_FOR_PURCHASE' if state['compliance_score'] == 1.0 else 'REJECTED'}

graph = StateGraph(InfusionState)
graph.add_node('validate', validate_medical_specs)
graph.add_node('finalize', finalize_procurement)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
