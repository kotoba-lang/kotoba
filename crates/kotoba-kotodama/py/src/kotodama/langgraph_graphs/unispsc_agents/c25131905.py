from typing import TypedDict
from langgraph.graph import StateGraph, END

class ASWHeliState(TypedDict):
    spec_compliance: bool
    export_approved: bool
    security_cleared: bool

def validate_tech_specs(state: ASWHeliState):
    state['spec_compliance'] = True
    return state

def check_export_controls(state: ASWHeliState):
    state['export_approved'] = True
    return state

graph = StateGraph(ASWHeliState)
graph.add_node('validate', validate_tech_specs)
graph.add_node('export', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'export')
graph.add_edge('export', END)
graph = graph.compile()
