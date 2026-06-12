from typing import TypedDict
from langgraph.graph import StateGraph, END

class HardwareState(TypedDict):
    spec_checked: bool
    compliance_score: float

def validate_dimensions(state: HardwareState):
    return {'spec_checked': True}

def assess_quality(state: HardwareState):
    return {'compliance_score': 1.0}

graph = StateGraph(HardwareState)
graph.add_node('validate', validate_dimensions)
graph.add_node('assess', assess_quality)
graph.set_entry_point('validate')
graph.add_edge('validate', 'assess')
graph.add_edge('assess', END)
graph = graph.compile()
