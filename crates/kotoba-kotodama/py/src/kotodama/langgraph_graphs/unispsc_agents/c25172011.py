from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ShockAbsorberState(TypedDict):
    part_number: str
    spec_compliance: bool
    test_report_url: str

def validate_specs(state: ShockAbsorberState):
    # Simulate CAD/Spec validation for shock absorber force requirements
    state['spec_compliance'] = True if state.get('part_number') else False
    return state

def verify_quality(state: ShockAbsorberState):
    # Simulate quality inspection verification
    return {'spec_compliance': state['spec_compliance'] and state.get('test_report_url') is not None}

graph = StateGraph(ShockAbsorberState)
graph.add_node('validate', validate_specs)
graph.add_node('verify', verify_quality)
graph.set_entry_point('validate')
graph.add_edge('validate', 'verify')
graph.add_edge('verify', END)
graph = graph.compile()
