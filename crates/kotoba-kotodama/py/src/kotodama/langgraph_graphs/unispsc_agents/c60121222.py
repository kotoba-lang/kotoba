from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class PaintSpecState(TypedDict):
    product_name: str
    safety_compliant: bool
    lightfastness: int

def validate_safety(state: PaintSpecState):
    # Simulate toxicity check
    return {'safety_compliant': True}

def check_quality(state: PaintSpecState):
    # Simulate lightfastness validation
    return {'lightfastness': 5}

graph = StateGraph(PaintSpecState)
graph.add_node('safety_check', validate_safety)
graph.add_node('quality_check', check_quality)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'quality_check')
graph.add_edge('quality_check', END)
graph = graph.compile()
