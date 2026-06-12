from typing import TypedDict
from langgraph.graph import StateGraph, END

class AlloyState(TypedDict):
    material_spec: dict
    compliance_check: bool
    approved: bool

def validate_composition(state: AlloyState):
    # Simulate chemical property validation logic
    specs = state.get('material_spec', {})
    is_compliant = all(key in specs for key in ['carbon_content', 'tensile_strength'])
    print(f'Validating alloy composition: {is_compliant}')
    return {'compliance_check': is_compliant}

def approve_procurement(state: AlloyState):
    return {'approved': state['compliance_check']}

graph = StateGraph(AlloyState)
graph.add_node('validate', validate_composition)
graph.add_node('approve', approve_procurement)
graph.add_edge('validate', 'approve')
graph.add_edge('approve', END)
graph.set_entry_point('validate')
graph = graph.compile()
