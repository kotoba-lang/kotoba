from typing import TypedDict
from langgraph.graph import StateGraph, END

class OtoscopeState(TypedDict):
    spec_compliance: bool
    sterilization_verified: bool
    final_approval: bool

def validate_spec_compliance(state: OtoscopeState):
    return {'spec_compliance': True} if 'material_type' in state else {'spec_compliance': False}

def verify_sterilization(state: OtoscopeState):
    return {'sterilization_verified': True}

graph = StateGraph(OtoscopeState)
graph.add_node('validate', validate_spec_compliance)
graph.add_node('sterilize_check', verify_sterilization)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterilize_check')
graph.add_edge('sterilize_check', END)
graph = graph.compile()
