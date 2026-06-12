from langgraph.graph import StateGraph, END
from typing import TypedDict, List

class ProcurementState(TypedDict):
    item_name: str
    compliance_check: bool
    spec_verified: bool

def validate_materials(state: ProcurementState):
    print('Validating materials for shoe accessories...')
    state['compliance_check'] = True
    return state

def check_dimensions(state: ProcurementState):
    print('Verifying dimensional accuracy of components...')
    state['spec_verified'] = True
    return state

graph = StateGraph(ProcurementState)
graph.add_node('material_check', validate_materials)
graph.add_node('dimension_check', check_dimensions)
graph.set_entry_point('material_check')
graph.add_edge('material_check', 'dimension_check')
graph.add_edge('dimension_check', END)
graph = graph.compile()
