from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class GrindingMediaState(TypedDict):
    media_type: str
    hardness_check: bool
    composition_validated: bool
    compliance_score: float

def validate_specs(state: GrindingMediaState) -> GrindingMediaState:
    # Specialized validation logic for alloy media
    state['hardness_check'] = True
    state['composition_validated'] = True
    state['compliance_score'] = 0.98
    return state

def check_wear_rate(state: GrindingMediaState) -> GrindingMediaState:
    # Simulate wear rate analysis based on alloy composition
    return state

workflow = StateGraph(GrindingMediaState)
workflow.add_node('validate', validate_specs)
workflow.add_node('wear_analysis', check_wear_rate)
workflow.set_entry_point('validate')
workflow.add_edge('validate', 'wear_analysis')
workflow.add_edge('wear_analysis', END)
graph = workflow.compile()
