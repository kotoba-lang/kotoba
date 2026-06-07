from typing import TypedDict
from langgraph.graph import StateGraph, END

class CameraState(TypedDict):
    model_name: str
    resolution_check: bool
    is_approved: bool

def validate_specs(state: CameraState):
    # Simulate spec validation logic for document cameras
    state['resolution_check'] = True
    return {'resolution_check': True}

def approve_procurement(state: CameraState):
    state['is_approved'] = state.get('resolution_check', False)
    return {'is_approved': True}

workflow = StateGraph(CameraState)
workflow.add_node('validate', validate_specs)
workflow.add_node('approve', approve_procurement)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'approve')
workflow.add_edge('approve', END)
graph = workflow.compile()
