from typing import TypedDict
from langgraph.graph import StateGraph, END

class ToolingState(TypedDict):
    spec_check: bool
    export_control_ok: bool

def validate_specs(state: ToolingState):
    return {'spec_check': True}

def check_export(state: ToolingState):
    return {'export_control_ok': True}

graph = StateGraph(ToolingState)
graph.add_node('validate', validate_specs)
graph.add_node('export', check_export)
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph.set_entry_point('validate')
graph = graph.compile()
