from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    ring_spec: dict
    validation_passed: bool

def validate_ring_specs(state: ProcurementState):
    spec = state.get('ring_spec', {})
    required = ['material_composition', 'ring_diameter_mm']
    passed = all(k in spec for k in required)
    return {'validation_passed': passed}

def route_by_validation(state: ProcurementState):
    return 'process' if state['validation_passed'] else END

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_ring_specs)
graph.set_entry_point('validate')
graph.add_conditional_edges('validate', route_by_validation, {'process': END, END: END})
graph = graph.compile()
