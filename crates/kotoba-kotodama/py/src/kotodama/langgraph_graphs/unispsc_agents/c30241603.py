from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    material_data: dict
    validation_passed: bool

def validate_structural_specs(state: ProcurementState):
    specs = state.get('material_data', {})
    required = ['tensile_strength', 'material_grade']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

graph = StateGraph(ProcurementState)
graph.add_node('validation', validate_structural_specs)
graph.set_entry_point('validation')
graph.add_edge('validation', END)
graph = graph.compile()
