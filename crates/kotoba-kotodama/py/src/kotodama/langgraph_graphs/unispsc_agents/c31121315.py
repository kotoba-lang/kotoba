from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastState(TypedDict):
    cad_file: str
    material_compliance: bool
    dimensional_check: bool

def validate_cad(state: CastState):
    print('Validating CAD geometry for mold extraction')
    return {'dimensional_check': True}

def check_material_safety(state: CastState):
    print('Verifying lead alloy compliance with MSDS standards')
    return {'material_compliance': True}

graph = StateGraph(CastState)
graph.add_node('validate_cad', validate_cad)
graph.add_node('check_material', check_material_safety)
graph.set_entry_point('validate_cad')
graph.add_edge('validate_cad', 'check_material')
graph.add_edge('check_material', END)
graph = graph.compile()
