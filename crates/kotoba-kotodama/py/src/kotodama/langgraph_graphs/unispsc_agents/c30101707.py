from langgraph.graph import StateGraph, END
from typing import TypedDict

class MagnesiumSpecState(TypedDict):
    material_certified: bool
    passes_strength_test: bool
    export_license_required: bool

def validate_material(state: MagnesiumSpecState):
    state['material_certified'] = True
    return state

def perform_strength_test(state: MagnesiumSpecState):
    state['passes_strength_test'] = True
    return state

def check_export_compliance(state: MagnesiumSpecState):
    state['export_license_required'] = True
    return state

graph = StateGraph(MagnesiumSpecState)
graph.add_node('validate', validate_material)
graph.add_node('strength_test', perform_strength_test)
graph.add_node('export_check', check_export_compliance)
graph.set_entry_point('validate')
graph.add_edge('validate', 'strength_test')
graph.add_edge('strength_test', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
