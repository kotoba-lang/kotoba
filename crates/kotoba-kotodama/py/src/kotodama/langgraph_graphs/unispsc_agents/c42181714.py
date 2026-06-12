from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class EKGSpecState(TypedDict):
    part_number: str
    compatibility_verified: bool
    compliance_docs: List[str]
    validation_status: str

def validate_tech_specs(state: EKGSpecState):
    # Simulate logic for validating medical grade compatibility
    state['compatibility_verified'] = True if 'IEC60601' in state.get('compliance_docs', []) else False
    return {'validation_status': 'APPROVED' if state['compatibility_verified'] else 'REJECTED'}

graph = StateGraph(EKGSpecState)
graph.add_node('validate', validate_tech_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
