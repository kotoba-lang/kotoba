from typing import TypedDict
from langgraph.graph import StateGraph, END

class ProcurementState(TypedDict):
    item: str
    validation_checks: list
    status: str

def validate_adhesive_specs(state: ProcurementState):
    checks = ['check_adhesive_residue', 'check_dimensions', 'check_material_safety']
    return {'validation_checks': checks, 'status': 'validated'}

def update_inventory(state: ProcurementState):
    return {'status': 'processed'}

graph = StateGraph(ProcurementState)
graph.add_node('validate', validate_adhesive_specs)
graph.add_node('inventory', update_inventory)
graph.set_entry_point('validate')
graph.add_edge('validate', 'inventory')
graph.add_edge('inventory', END)
graph = graph.compile()
