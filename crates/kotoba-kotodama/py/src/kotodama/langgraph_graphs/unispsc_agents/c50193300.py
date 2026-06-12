from typing import TypedDict
from langgraph.graph import StateGraph, END

class CitrusState(TypedDict):
    quality_score: float
    food_safety_compliant: bool
    batch_id: str

def validate_batch(state: CitrusState):
    if state.get('quality_score', 0) < 0.8:
        return 'REJECT'
    return 'APPROVE'

def process_batch(state):
    print(f'Processing batch {state.get('batch_id')} for inventory.')
    return {'quality_score': 1.0}

graph = StateGraph(CitrusState)
graph.add_node('process', process_batch)
graph.set_entry_point('process')
graph.add_edge('process', END)
graph = graph.compile()
