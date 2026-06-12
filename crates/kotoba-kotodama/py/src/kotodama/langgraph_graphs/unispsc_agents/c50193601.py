from typing import TypedDict
from langgraph.graph import StateGraph, END

class CherryProcurementState(TypedDict):
    quality_score: float
    safety_check: bool
    is_approved: bool

def validate_quality(state: CherryProcurementState):
    # Simulate quality inspection logic for processed food
    state['safety_check'] = state.get('quality_score', 0) > 0.8
    return {'safety_check': state['safety_check']}

def final_approval(state: CherryProcurementState):
    state['is_approved'] = state['safety_check']
    return {'is_approved': state['is_approved']}

graph_builder = StateGraph(CherryProcurementState)
graph_builder.add_node('validate', validate_quality)
graph_builder.add_node('approval', final_approval)
graph_builder.set_entry_point('validate')
graph_builder.add_edge('validate', 'approval')
graph_builder.add_edge('approval', END)
graph = graph_builder.compile()
