from typing import TypedDict
from langgraph.graph import StateGraph, END

class PullToyState(TypedDict):
    safety_check: bool
    toxicity_test: bool
    design_approved: bool

def validate_safety(state: PullToyState):
    return {'safety_check': True}

def validate_materials(state: PullToyState):
    return {'toxicity_test': True}

def execute_final_review(state: PullToyState):
    return {'design_approved': True}

graph = StateGraph(PullToyState)
graph.add_node('safety_check', validate_safety)
graph.add_node('toxicity_test', validate_materials)
graph.add_node('final_review', execute_final_review)
graph.set_entry_point('safety_check')
graph.add_edge('safety_check', 'toxicity_test')
graph.add_edge('toxicity_test', 'final_review')
graph.add_edge('final_review', END)
graph = graph.compile()
