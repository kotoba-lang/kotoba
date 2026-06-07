from typing import TypedDict
from langgraph.graph import StateGraph, END

class MathKitState(TypedDict):
    material_certified: bool
    safety_passed: bool
    is_approved: bool

def validate_safety(state: MathKitState):
    is_safe = state.get('material_certified', False) and state.get('safety_passed', False)
    return {'is_approved': is_safe}

def decision_node(state: MathKitState):
    return 'approved' if state['is_approved'] else 'rejected'

graph = StateGraph(MathKitState)
graph.add_node('validate', validate_safety)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', decision_node, {'approved': END, 'rejected': END})
graph = graph.compile()
