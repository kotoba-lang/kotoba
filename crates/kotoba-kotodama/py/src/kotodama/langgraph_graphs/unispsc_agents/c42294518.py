from typing import TypedDict
from langgraph.graph import StateGraph, END

class OpticalState(TypedDict):
    part_specs: dict
    validation_passed: bool
    error_log: list

def validate_specs(state: OpticalState):
    specs = state.get('part_specs', {})
    required = ['dimensional_tolerance_microns', 'material_grade']
    passed = all(key in specs for key in required)
    return {'validation_passed': passed}

def export_control_check(state: OpticalState):
    # Simulate export control compliance logic
    return {'validation_passed': state['validation_passed'] and True}

graph = StateGraph(OpticalState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', export_control_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
