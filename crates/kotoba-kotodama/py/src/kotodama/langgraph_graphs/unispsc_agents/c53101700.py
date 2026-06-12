from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class GarmentState(TypedDict):
    sku_id: str
    inspection_passed: bool
    compliance_docs: List[str]

def validate_materials(state: GarmentState):
    # Business logic for material validation
    return {'inspection_passed': True}

def check_compliance(state: GarmentState):
    # Logic for checking certificates
    return {'compliance_docs': ['ISO_textile_standard']}

graph = StateGraph(GarmentState)
graph.add_node('material_check', validate_materials)
graph.add_node('compliance_check', check_compliance)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'compliance_check')
graph.add_edge('compliance_check', END)
graph = graph.compile()
