from typing import TypedDict
from langgraph.graph import StateGraph, END

class FurnitureWorkflowState(TypedDict):
    item_name: str
    material_compliance: bool
    assembly_required: bool
    status: str

def validate_specs(state: FurnitureWorkflowState):
    compliance = state.get('material_compliance', False)
    return {'status': 'Validated' if compliance else 'Rejected'}

def assembly_check(state: FurnitureWorkflowState):
    return {'status': 'Arranging Technician' if state.get('assembly_required') else 'Ready for Shipment'}

graph = StateGraph(FurnitureWorkflowState)
graph.add_node('validate', validate_specs)
graph.add_node('assembly', assembly_check)
graph.add_edge('validate', 'assembly')
graph.add_edge('assembly', END)
graph.set_entry_point('validate')
graph = graph.compile()
