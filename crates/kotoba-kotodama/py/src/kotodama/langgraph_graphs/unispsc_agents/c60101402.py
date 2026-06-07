from typing import TypedDict
from langgraph.graph import StateGraph, END

class AwardProcurementState(TypedDict):
    design_file: str
    material_spec: str
    approval_status: bool

def validate_design(state: AwardProcurementState):
    print('Validating design dimensions...')
    return {'approval_status': True}

def check_material(state: AwardProcurementState):
    print('Verifying material compliance...')
    return {'approval_status': True}

graph = StateGraph(AwardProcurementState)
graph.add_node('validate', validate_design)
graph.add_node('material', check_material)
graph.add_edge('validate', 'material')
graph.add_edge('material', END)
graph.set_entry_point('validate')
graph = graph.compile()
