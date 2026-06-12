from typing import TypedDict
from langgraph.graph import StateGraph, END

class VtcState(TypedDict):
    spec_sheet: dict
    validation_results: list
    is_compliant: bool

def validate_specs(state: VtcState):
    specs = state.get('spec_sheet', {})
    checks = [specs.get('max_weight', 0) > 0, specs.get('spindle_speed') is not None]
    return {'validation_results': checks, 'is_compliant': all(checks)}

def export_check(state: VtcState):
    # Simplified dual-use check logic
    return {'is_compliant': state.get('is_compliant', False)}

graph = StateGraph(VtcState)
graph.add_node('validate', validate_specs)
graph.add_node('export_review', export_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_review')
graph.add_edge('export_review', END)
graph = graph.compile()
