from typing import TypedDict
from langgraph.graph import StateGraph, END

class CreosoteState(TypedDict):
    purity: float
    has_msds: bool
    is_hazmat_approved: bool
    status: str

def validate_safety_specs(state: CreosoteState):
    if not state.get('has_msds') or not state.get('is_hazmat_approved'):
        return {'status': 'REJECTED_SAFETY_VIOLATION'}
    return {'status': 'VALIDATED'}

workflow = StateGraph(CreosoteState)
workflow.add_node('safety_check', validate_safety_specs)
workflow.set_entry_point('safety_check')
workflow.add_edge('safety_check', END)
graph = workflow.compile()
