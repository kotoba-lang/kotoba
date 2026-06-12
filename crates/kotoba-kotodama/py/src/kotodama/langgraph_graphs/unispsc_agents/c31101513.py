from typing import TypedDict
from langgraph.graph import StateGraph, END

class DieCastingState(TypedDict):
    spec_file: str
    validation_passed: bool
    is_dual_use: bool

def validate_alloy_specs(state: DieCastingState):
    # Simulate CAD/Spec validation for copper die castings
    state['validation_passed'] = True
    return {'validation_passed': True}

def check_export_compliance(state: DieCastingState):
    # Simulate dual-use regulatory screening
    state['is_dual_use'] = True
    return {'is_dual_use': True}

graph = StateGraph(DieCastingState)
graph.add_node('ValidateSpecs', validate_alloy_specs)
graph.add_node('CheckCompliance', check_export_compliance)
graph.set_entry_point('ValidateSpecs')
graph.add_edge('ValidateSpecs', 'CheckCompliance')
graph.add_edge('CheckCompliance', END)
graph = graph.compile()
