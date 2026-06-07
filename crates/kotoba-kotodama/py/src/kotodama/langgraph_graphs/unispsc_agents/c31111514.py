from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class SteelState(TypedDict):
    material_code: str
    spec_check: bool
    compliance_risk: bool
    approved: bool

def validate_specs(state: SteelState):
    # Simulate CAD/Spec validation logic
    state['spec_check'] = state.get('material_code', '').startswith('ST')
    return state

def check_compliance(state: SteelState):
    # Check for dual-use export control restrictions
    state['compliance_risk'] = False
    state['approved'] = state['spec_check'] and not state['compliance_risk']
    return state

graph = StateGraph(SteelState)
graph.add_node('val', validate_specs)
graph.add_node('comp', check_compliance)
graph.set_entry_point('val')
graph.add_edge('val', 'comp')
graph.add_edge('comp', END)
graph = graph.compile()
