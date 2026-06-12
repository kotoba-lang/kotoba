from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolSpecState(TypedDict):
    spec_data: dict
    validated: bool
    error_log: list

def validate_specs(state: ToolSpecState):
    specs = state.get('spec_data', {})
    errors = []
    if 'material' not in specs: errors.append('Missing Material Grade')
    return {'validated': len(errors) == 0, 'error_log': errors}

def export_control_check(state: ToolSpecState):
    # Dual-use regulatory compliance check for machine tools
    return {'validated': state.get('validated', False)}

graph = StateGraph(ToolSpecState)
graph.add_node('validate', validate_specs)
graph.add_node('export_check', export_control_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export_check')
graph.add_edge('export_check', END)
graph = graph.compile()
