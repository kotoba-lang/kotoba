from typing import TypedDict
from langgraph.graph import StateGraph, END

class FoodState(TypedDict):
    quality_score: float
    meets_standards: bool
    approved: bool

def validate_purity(state: FoodState):
    state['meets_standards'] = state.get('quality_score', 0) > 0.9
    return state

def approval_step(state: FoodState):
    state['approved'] = state['meets_standards']
    return state

graph = StateGraph(FoodState)
graph.add_node('validate', validate_purity)
graph.add_node('approve', approval_step)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
