from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MiningState(TypedDict):
    equipment_id: str
    spec_data: dict
    validation_errors: List[str]
    is_approved: bool

def validate_specs(state: MiningState):
    errors = []
    if not state.get('spec_data', {}).get('explosion_proof_certification'):
        errors.append('Missing explosion proof certification')
    return {'validation_errors': errors, 'is_approved': len(errors) == 0}

def route_by_validation(state: MiningState):
    return 'APPROVED' if state['is_approved'] else 'REJECTED'

graph = StateGraph(MiningState)
graph.add_node('validate', validate_specs)
graph.add_edge('validate', END)
graph.set_entry_point('validate')

graph = graph.compile()
