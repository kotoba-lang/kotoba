from typing import TypedDict
from langgraph.graph import StateGraph, END

class PipeAssemblyState(TypedDict):
    spec_compliance: bool
    pressure_test_passed: bool
    material_certified: bool

def validate_materials(state: PipeAssemblyState):
    state['material_certified'] = True
    return state

def validate_assembly(state: PipeAssemblyState):
    state['spec_compliance'] = True
    state['pressure_test_passed'] = True
    return state

workflow = StateGraph(PipeAssemblyState)
workflow.add_node('material_check', validate_materials)
workflow.add_node('assembly_check', validate_assembly)
workflow.set_entry_point('material_check')
workflow.add_edge('material_check', 'assembly_check')
workflow.add_edge('assembly_check', END)
graph = workflow.compile()
