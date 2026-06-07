from typing import TypedDict
from langgraph.graph import StateGraph, END

class LotionApplicatorState(TypedDict):
    product_id: str
    safety_check: bool
    usability_score: float

def validate_safety(state: LotionApplicatorState) -> LotionApplicatorState:
    state['safety_check'] = True
    return state

def evaluate_ergonomics(state: LotionApplicatorState) -> LotionApplicatorState:
    state['usability_score'] = 9.5
    return state

graph = StateGraph(LotionApplicatorState)
graph.add_node('safety_check', validate_safety)
graph.add_node('ergonomics', evaluate_ergonomics)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'ergonomics')
graph.add_edge('ergonomics', END)
graph = graph.compile()
