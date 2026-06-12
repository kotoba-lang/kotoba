from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END

class MetalPowderState(TypedDict):
    purity_cert: bool
    particle_check_passed: bool
    safety_compliance: bool
    approved: bool

def validate_purity(state: MetalPowderState):
    # Simulate chemical analysis validation
    state['purity_cert'] = True
    return state

def validate_particle_size(state: MetalPowderState):
    # Simulate laser diffraction analysis
    state['particle_check_passed'] = True
    return state

def safety_gate(state: MetalPowderState):
    state['safety_compliance'] = True
    state['approved'] = all([state['purity_cert'], state['particle_check_passed'], state['safety_compliance']])
    return state

graph = StateGraph(MetalPowderState)
graph.add_node("validate_purity", validate_purity)
graph.add_node("validate_particle_size", validate_particle_size)
graph.add_node("safety_gate", safety_gate)
graph.set_entry_point("validate_purity")
graph.add_edge("validate_purity", "validate_particle_size")
graph.add_edge("validate_particle_size", "safety_gate")
graph.add_edge("safety_gate", END)
graph = graph.compile()
