from typing import TypedDict
from langgraph.graph import StateGraph, END

class MillingState(TypedDict):
    spec_data: dict
    validation_results: list
    is_compliant: bool

def validate_specs(state: MillingState):
    specs = state.get('spec_data', {})
    results = []
    if 'spindle_speed' not in specs: results.append('Missing spindle speed')
    return {'validation_results': results, 'is_compliant': len(results) == 0}

def check_export_control(state: MillingState):
    return {'validation_results': state['validation_results'] + ['Export control verified']}

graph = StateGraph(MillingState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_export_control)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()
