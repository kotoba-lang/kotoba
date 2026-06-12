from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    lifter_type: str
    capacity_check: bool
    safety_compliance: bool

def validate_capacity(state: State):
    capacity = state.get('capacity_check', False)
    return {'capacity_check': capacity}

def verify_safety_specs(state: State):
    compliance = state.get('safety_compliance', False)
    return {'safety_compliance': compliance}

graph = StateGraph(State)
graph.add_node('validate_capacity', validate_capacity)
graph.add_node('verify_safety_specs', verify_safety_specs)
graph.set_entry_point('validate_capacity')
graph.add_edge('validate_capacity', 'verify_safety_specs')
graph.add_edge('verify_safety_specs', END)
graph = graph.compile()
