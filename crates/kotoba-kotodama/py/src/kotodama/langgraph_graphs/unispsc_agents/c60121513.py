from typing import TypedDict
from langgraph.graph import StateGraph, END

class ArtSupplyState(TypedDict):
    product_name: str
    safety_check: bool
    quality_score: float

def validate_safety(state: ArtSupplyState):
    state['safety_check'] = True
    return state

def assess_quality(state: ArtSupplyState):
    state['quality_score'] = 9.5
    return state

graph = StateGraph(ArtSupplyState)
graph.add_node('validate_safety', validate_safety)
graph.add_node('assess_quality', assess_quality)
graph.set_entry_point('validate_safety')
graph.add_edge('validate_safety', 'assess_quality')
graph.add_edge('assess_quality', END)
graph = graph.compile()
