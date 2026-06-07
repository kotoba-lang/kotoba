from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GuillotineState(TypedDict):
    specs: dict
    validation_passed: bool
    safety_check_log: List[str]

def validate_safety_protocols(state: GuillotineState):
    specs = state.get('specs', {})
    checks = []
    if specs.get('has_dual_hand_control'):
        checks.append('Safety control verified')
    return {'safety_check_log': checks, 'validation_passed': len(checks) > 0}

def approval_step(state: GuillotineState):
    return {'validation_passed': True}

graph = StateGraph(GuillotineState)
graph.add_node('safety', validate_safety_protocols)
graph.add_node('approval', approval_step)
graph.set_entry_point('safety')
graph.add_edge('safety', 'approval')
graph.add_edge('approval', END)
graph = graph.compile()
