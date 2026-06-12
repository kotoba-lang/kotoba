from langgraph.graph import StateGraph, END
from typing import TypedDict

class BearingState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_dimensions(state: BearingState):
    """Validate dimensional tolerances for sleeve bearings."""
    spec = state.get('spec_data', {})
    # Logic for tolerance checking
    passed = 'inner_dia' in spec and 'outer_dia' in spec
    return {'validation_passed': passed}

def check_material_compliance(state: BearingState):
    """Ensure material meets ISO/JIS standards."""
    return {'validation_passed': state['validation_passed']}

graph = StateGraph(BearingState)
graph.add_node('validate', validate_dimensions)
graph.add_node('compliance', check_material_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
