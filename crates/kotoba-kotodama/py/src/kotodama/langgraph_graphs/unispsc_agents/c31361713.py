from typing import TypedDict
from langgraph.graph import StateGraph, END

class AssemblyState(TypedDict):
    material_certified: bool
    torque_tested: bool
    assembly_verified: bool

def validate_material(state: AssemblyState):
    state['material_certified'] = True
    return state

def run_torque_test(state: AssemblyState):
    state['torque_tested'] = True
    return state

def verify_assembly(state: AssemblyState):
    state['assembly_verified'] = True
    return state

graph = StateGraph(AssemblyState)
graph.add_node('MaterialValidation', validate_material)
graph.add_node('TorqueTest', run_torque_test)
graph.add_node('FinalVerification', verify_assembly)
graph.set_entry_point('MaterialValidation')
graph.add_edge('MaterialValidation', 'TorqueTest')
graph.add_edge('TorqueTest', 'FinalVerification')
graph.add_edge('FinalVerification', END)
graph = graph.compile()
