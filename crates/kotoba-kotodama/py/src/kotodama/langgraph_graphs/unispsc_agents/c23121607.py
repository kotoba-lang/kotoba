from typing import TypedDict
from langgraph.graph import StateGraph, END

class LaserProcState(TypedDict):
    machine_specs: dict
    validation_results: dict
    is_compliant: bool

def validate_safety(state: LaserProcState):
    # Business logic for laser equipment safety check
    specs = state.get('machine_specs', {})
    state['is_compliant'] = specs.get('iso_safety_level', 0) >= 4
    return state

def check_export_controls(state: LaserProcState):
    # Dual-use export logic
    state['validation_results'] = {'export_license_required': True}
    return state

graph = StateGraph(LaserProcState)
graph.add_node('safety_check', validate_safety)
graph.add_node('export_review', check_export_controls)
graph.add_edge('safety_check', 'export_review')
graph.add_edge('export_review', END)
graph.set_entry_point('safety_check')
graph = graph.compile()
