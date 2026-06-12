from typing import TypedDict
from langgraph.graph import StateGraph, END

class SafetyTapeState(TypedDict):
    material_specs: dict
    compliance_checked: bool
    approved: bool

def validate_specs(state: SafetyTapeState):
    specs = state.get('material_specs', {})
    is_valid = all(key in specs for key in ['reflectivity', 'tensile_strength'])
    return {'compliance_checked': True, 'approved': is_valid}

graph = StateGraph(SafetyTapeState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)
graph = graph.compile()
