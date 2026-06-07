from typing import TypedDict
from langgraph.graph import StateGraph, END

class CopperAssemblyState(TypedDict):
    spec_data: dict
    validation_passed: bool
    error_log: list

def validate_welding_specs(state: CopperAssemblyState):
    specs = state.get('spec_data', {})
    required = ['material_purity', 'shear_strength']
    passed = all(k in specs for k in required)
    return {'validation_passed': passed}

def process_assembly(state: CopperAssemblyState):
    # Simulate CAD/Engineering check workflow
    return {'error_log': ['Passed thermal conductivity check'] if state['validation_passed'] else ['Mismatch']}

graph = StateGraph(CopperAssemblyState)
graph.add_node('validate', validate_welding_specs)
graph.add_node('process', process_assembly)
graph.set_entry_point('validate')
graph.add_edge('validate', 'process')
graph.add_edge('process', END)
graph = graph.compile()
