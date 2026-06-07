from typing import TypedDict
from langgraph.graph import StateGraph, END

class PaintState(TypedDict):
    paint_type: str
    toxicity_passed: bool
    viscosity_check: bool

def validate_safety(state: PaintState):
    return {'toxicity_passed': True}

def check_consistency(state: PaintState):
    return {'viscosity_check': True}

graph = StateGraph(PaintState)
graph.add_node('safety', validate_safety)
graph.add_node('viscosity', check_consistency)
graph.set_entry_point('safety')
graph.add_edge('safety', 'viscosity')
graph.add_edge('viscosity', END)
graph = graph.compile()
