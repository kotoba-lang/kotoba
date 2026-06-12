from typing import TypedDict, List
from langgraph.graph import StateGraph, END

class ToolState(TypedDict):
    specs: dict
    validated: bool
    compliance_report: str

def validate_specs(state: ToolState):
    specs = state.get('specs', {})
    is_valid = all(k in specs for k in ['precision', 'material'])
    return {'validated': is_valid, 'compliance_report': 'Passed' if is_valid else 'Failed'}

def export_check(state: ToolState):
    return {'compliance_report': state['compliance_report'] + ' - Export Control Checked'}

graph = StateGraph(ToolState)
graph.add_node('validate', validate_specs)
graph.add_node('export', export_check)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()
