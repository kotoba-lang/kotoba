from typing import TypedDict
from langgraph.graph import StateGraph, END

class PipeAssemblyState(TypedDict):
    spec_data: dict
    is_compliant: bool
    validation_log: list

def validate_specs(state: PipeAssemblyState):
    specs = state.get('spec_data', {})
    log = []
    compliant = True
    if 'material_grade' not in specs:
        log.append('Missing mandatory ASTM material grade')
        compliant = False
    return {'is_compliant': compliant, 'validation_log': log}

def structural_integrity_check(state: PipeAssemblyState):
    # Simulate CAD/FEA validation integration
    return {'validation_log': state.get('validation_log', []) + ['Structural integrity verified']}

graph = StateGraph(PipeAssemblyState)
graph.add_node('validate', validate_specs)
graph.add_node('integrity_check', structural_integrity_check)
graph.add_edge('validate', 'integrity_check')
graph.add_edge('integrity_check', END)
graph.set_entry_point('validate')
graph.set_entry_point('validate')

graph = graph.compile()
