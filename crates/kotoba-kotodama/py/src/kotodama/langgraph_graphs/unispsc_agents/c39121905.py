from typing import TypedDict
from langgraph.graph import StateGraph, END

class LockoutState(TypedDict):
    device_type: str
    material_compliance: bool
    validation_passed: bool

def validate_safety_spec(state: LockoutState):
    # Simulate validation of locking mechanism specs
    spec_valid = state.get('material_compliance', False)
    return {'validation_passed': spec_valid}

graph = StateGraph(LockoutState)
graph.add_node('validate', validate_safety_spec)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
