from typing import TypedDict
from langgraph.graph import StateGraph, END

class ChassisState(TypedDict):
    spec_data: dict
    validation_score: float
    needs_manual_review: bool

def validate_specs(state: ChassisState):
    specs = state.get('spec_data', {})
    score = 1.0 if all(key in specs for key in ['material', 'weld_cert']) else 0.5
    return {'validation_score': score, 'needs_manual_review': score < 1.0}

def route_review(state: ChassisState):
    return 'review' if state['needs_manual_review'] else 'complete'

graph = StateGraph(ChassisState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_review, {'review': END, 'complete': END})
graph.add_edge('validate', END)
graph = graph.compile()
