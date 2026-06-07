from typing import TypedDict
from langgraph.graph import StateGraph, END

class RacketProcurementState(TypedDict):
    racket_specs: dict
    validation_passed: bool

def validate_materials(state: RacketProcurementState):
    specs = state.get('racket_specs', {})
    required = ['frame_material', 'weight']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def approval_node(state: RacketProcurementState):
    return {'validation_passed': True}

graph = StateGraph(RacketProcurementState)
graph.add_node('validate', validate_materials)
graph.add_node('approve', approval_node)
graph.set_entry_point('validate')
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph = graph.compile()
