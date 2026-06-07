from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class MathKitState(TypedDict):
    kit_id: str
    safety_check: bool
    components_verified: bool
    approved: bool

def validate_components(state: MathKitState):
    return {'components_verified': True}

def safety_review(state: MathKitState):
    return {'safety_check': True}

def finalize_kit(state: MathKitState):
    return {'approved': state['components_verified'] and state['safety_check']}

graph = StateGraph(MathKitState)
graph.add_node('validate', validate_components)
graph.add_node('safety', safety_review)
graph.add_node('finalize', finalize_kit)
graph.set_entry_point('validate')
graph.add_edge('validate', 'safety')
graph.add_edge('safety', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
