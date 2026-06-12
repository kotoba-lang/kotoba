from typing import TypedDict
from langgraph.graph import StateGraph, END

class CastingState(TypedDict):
    material_spec: str
    cad_file_verified: bool
    inspection_passed: bool

def validate_cad(state: CastingState):
    print('Validating CAD dimensions for sand casting constraints...')
    return {'cad_file_verified': True}

def check_metallurgy(state: CastingState):
    print('Verifying non-ferrous alloy composition...')
    return {'inspection_passed': True}

graph = StateGraph(CastingState)
graph.add_node('cad_validation', validate_cad)
graph.add_node('metallurgy_check', check_metallurgy)
graph.set_entry_point('cad_validation')
graph.add_edge('cad_validation', 'metallurgy_check')
graph.add_edge('metallurgy_check', END)

graph = graph.compile()
