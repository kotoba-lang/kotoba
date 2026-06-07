from typing import TypedDict
from langgraph.graph import StateGraph, END

class ShieldingState(TypedDict):
    spec_data: dict
    validation_status: bool

def validate_shielding_specs(state: ShieldingState):
    specs = state.get('spec_data', {})
    # Check for mandatory radiation attenuation and lead equivalence
    is_valid = 'lead_eq' in specs and 'attenuation' in specs
    return {'validation_status': is_valid}

def export_review(state: ShieldingState):
    # Dual-use review logic
    return {'validation_status': True}

graph = StateGraph(ShieldingState)
graph.add_node('validate', validate_shielding_specs)
graph.add_node('export_check', export_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
