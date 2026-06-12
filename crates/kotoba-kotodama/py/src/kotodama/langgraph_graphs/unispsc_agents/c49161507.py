from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: ProcurementState):
    specs = state.get('spec_data', {})
    # Check for required safety and durability dimensions
    required_fields = ['dimensions', 'material', 'mounting_hardware']
    is_compliant = all(field in specs for field in required_fields)
    return {'is_compliant': is_compliant, 'validation_log': ['Dimensions verified' if is_compliant else 'Missing specs']}

def route_procurement(state: ProcurementState):
    return 'APPROVED' if state['is_compliant'] else 'REJECTED'

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_specs)
graph.set_entry_point('validate')
graph.add_edge('validate', END)

graph = graph.compile()
