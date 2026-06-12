from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class TapeProcurementState(TypedDict):
    tape_type: str
    specifications: dict
    validation_passed: bool

def validate_tape_specs(state: TapeProcurementState):
    specs = state.get('specifications', {})
    required = ['adhesion', 'width']
    return {'validation_passed': all(k in specs for k in required)}

def finalize_order(state: TapeProcurementState):
    return {'validation_passed': True}

graph = StateGraph(TapeProcurementState)
graph.add_node('validate', validate_tape_specs)
graph.add_node('finalize', finalize_order)
graph.set_entry_point('validate')
graph.add_edge('validate', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
