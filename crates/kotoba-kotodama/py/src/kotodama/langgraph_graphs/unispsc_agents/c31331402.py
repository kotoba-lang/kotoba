from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    assembly_id: str
    material_spec_ok: bool
    weld_quality_certified: bool
    approved: bool

def validate_materials(state: AssemblyState):
    # Simulate material compliance check
    return {'material_spec_ok': True}

def verify_welds(state: AssemblyState):
    # Simulate UV welding inspection process
    return {'weld_quality_certified': True}

def finalize_assembly(state: AssemblyState):
    is_ok = state['material_spec_ok'] and state['weld_quality_certified']
    return {'approved': is_ok}

graph = StateGraph(AssemblyState)
graph.add_node('validate_materials', validate_materials)
graph.add_node('verify_welds', verify_welds)
graph.add_node('finalize', finalize_assembly)
graph.set_entry_point('validate_materials')
graph.add_edge('validate_materials', 'verify_welds')
graph.add_edge('verify_welds', 'finalize')
graph.add_edge('finalize', END)
graph = graph.compile()
