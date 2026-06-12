from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class ResinState(TypedDict):
    batch_id: str
    quality_metrics: dict
    approved: bool

def validate_material(state: ResinState) -> ResinState:
    # Simulate CAD/Spec validation for synthetic resin
    metrics = state.get('quality_metrics', {})
    is_valid = metrics.get('tensile_strength', 0) > 500
    return {'approved': is_valid}

def route_to_qa(state: ResinState) -> str:
    return 'qa' if state['approved'] else 'reject'

workflow = StateGraph(ResinState)
workflow.add_node('validation', validate_material)
workflow.add_node('qa', lambda s: s)
workflow.add_node('reject', lambda s: s)

workflow.set_entry_point('validation')
workflow.add_conditional_edges('validation', route_to_qa)
workflow.add_edge('qa', END)
workflow.add_edge('reject', END)

graph = workflow.compile()
