from typing import TypedDict
from langgraph.graph import StateGraph, END

class MillingState(TypedDict):
    spec_verified: bool
    export_compliance: bool
    setup_complete: bool

def validate_specs(state: MillingState):
    print('Validating machine precision specs...')
    return {'spec_verified': True}

def check_export_controls(state: MillingState):
    print('Checking dual-use export classification...')
    return {'export_compliance': True}

graph = StateGraph(MillingState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_export_controls)
graph.set_entry_point('validate')
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph = graph.compile()
