from typing import TypedDict
from langgraph.graph import StateGraph, END

class BearingState(TypedDict):
    spec_data: dict
    validation_score: float
    status: str

def validate_bearing_spec(state: BearingState):
    specs = state.get('spec_data', {})
    score = 1.0 if 'Load Rating Capacity' in specs and 'Precision Tolerance Grade' in specs else 0.5
    return {'validation_score': score, 'status': 'VALIDATED' if score == 1.0 else 'REVIEW_REQUIRED'}

graph = StateGraph(BearingState)
graph.add_node('validate', validate_bearing_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
