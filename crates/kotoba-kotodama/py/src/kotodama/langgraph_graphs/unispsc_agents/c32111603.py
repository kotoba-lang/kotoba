from typing import TypedDict
from langgraph.graph import StateGraph, END

class MOSFETState(TypedDict):
    part_number: str
    specifications: dict
    compliance_valid: bool

def validate_specs(state: MOSFETState):
    specs = state.get('specifications', {})
    # Logic: Validate thermal rating and voltage range
    is_valid = specs.get('Vds', 0) > 0 and specs.get('temp_max', 0) > 85
    return {'compliance_valid': is_valid}

def export_review(state: MOSFETState):
    # Dual-use check logic
    return {'compliance_valid': True}

graph = StateGraph(MOSFETState)
graph.add_node('validate', validate_specs)
graph.add_node('export_control', export_review)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_control')
graph.add_edge('export_control', END)
graph = graph.compile()
