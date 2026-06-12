from typing import TypedDict
from langgraph.graph import StateGraph, END

class GCState(TypedDict):
    liner_specs: dict
    validation_passed: bool

def validate_liner_dimensions(state: GCState):
    # Simulate CAD-based dimensional check for GC liner fitment
    specs = state.get('liner_specs', {})
    passed = specs.get('id', 0) > 0 and specs.get('length', 0) > 0
    return {'validation_passed': passed}

def check_thermal_stability(state: GCState):
    # Simulate material deactivation validation
    return {'validation_passed': state['validation_passed']}

graph = StateGraph(GCState)
graph.add_node('validate_dims', validate_liner_dimensions)
graph.add_node('check_thermal', check_thermal_stability)
graph.set_entry_point('validate_dims')
graph.add_edge('validate_dims', 'check_thermal')
graph.add_edge('check_thermal', END)
graph = graph.compile()
