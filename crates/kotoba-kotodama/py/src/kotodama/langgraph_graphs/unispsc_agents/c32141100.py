from typing import TypedDict
from langgraph.graph import StateGraph, END

class ElectronTubeState(TypedDict):
    part_specs: dict
    validation_passed: bool
    is_dual_use: bool

def validate_specs(state: ElectronTubeState):
    specs = state.get('part_specs', {})
    # Logic to check vacuum integrity and material purity
    state['validation_passed'] = all(k in specs for k in ['material', 'vacuum_rating'])
    print('Validating electron tube component specifications...')
    return state

def check_export_controls(state: ElectronTubeState):
    # Dual-use classification check logic
    state['is_dual_use'] = state.get('part_specs', {}).get('is_military_grade', False)
    return state

graph = StateGraph(ElectronTubeState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
