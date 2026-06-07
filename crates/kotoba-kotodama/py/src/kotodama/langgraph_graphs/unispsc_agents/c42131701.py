from typing import TypedDict
from langgraph.graph import StateGraph, END

class SurgicalDrapeState(TypedDict):
    spec_compliance: bool
    sterilization_verified: bool
    traceability_code: str

def validate_specs(state: SurgicalDrapeState):
    state['spec_compliance'] = True
    return state

def check_sterilization(state: SurgicalDrapeState):
    state['sterilization_verified'] = True
    return state

graph = StateGraph(SurgicalDrapeState)
graph.add_node('validate', validate_specs)
graph.add_node('sterility_check', check_sterilization)
graph.set_entry_point('validate')
graph.add_edge('validate', 'sterility_check')
graph.add_edge('sterility_check', END)
graph = graph.compile()
