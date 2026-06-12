from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    validation_status: str
    approval_required: bool

def validate_clips(state: ProcurementState):
    specs = state.get('spec_data', {})
    if 'material_composition' in specs and 'sterilization_method' in specs:
        return {'validation_status': 'verified', 'approval_required': False}
    return {'validation_status': 'incomplete', 'approval_required': True}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_clips)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
