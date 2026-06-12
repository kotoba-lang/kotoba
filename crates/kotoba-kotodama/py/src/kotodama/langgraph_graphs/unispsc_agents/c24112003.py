from typing import TypedDict
from langgraph.graph import StateGraph, END

class BinProcurementState(TypedDict):
    bin_specs: dict
    validation_results: list
    is_approved: bool

def validate_load_capacity(state: BinProcurementState):
    capacity = state.get('bin_specs', {}).get('load_capacity_kg', 0)
    valid = capacity > 0
    return {'validation_results': [f'Capacity valid: {valid}']}

def check_compliance(state: BinProcurementState):
    material = state.get('bin_specs', {}).get('material_composition', '')
    status = 'FDA' in material or 'Industrial' in material
    return {'is_approved': status}

graph = StateGraph(BinProcurementState)
graph.add_node('validate', validate_load_capacity)
graph.add_node('compliance', check_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
