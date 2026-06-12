from typing import TypedDict, Annotated, Sequence
import operator
from langgraph.graph import StateGraph, END

class ResinState(TypedDict):
    batch_id: str
    composition_check: bool
    thermal_validation: bool
    is_compliant: bool

def validate_composition(state: ResinState) -> ResinState:
    # Logic to verify polymer chain integrity
    state['composition_check'] = True
    return state

def validate_thermal_specs(state: ResinState) -> ResinState:
    # Logic to check heat deflection temperature
    state['thermal_validation'] = True
    return state

def check_compliance(state: ResinState) -> ResinState:
    state['is_compliant'] = state['composition_check'] and state['thermal_validation']
    return state

graph = StateGraph(ResinState)
graph.add_node("composition", validate_composition)
graph.add_node("thermal", validate_thermal_specs)
graph.add_node("compliance", check_compliance)
graph.set_entry_point("composition")
graph.add_edge("composition", "thermal")
graph.add_edge("thermal", "compliance")
graph.add_edge("compliance", END)
graph = graph.compile()
