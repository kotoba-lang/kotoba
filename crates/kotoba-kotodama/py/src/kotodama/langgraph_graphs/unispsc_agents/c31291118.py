from typing import TypedDict
from langgraph.graph import StateGraph, END

class ExtrusionState(TypedDict):
    material_data: str
    tolerance_check: bool
    compliance_cleared: bool

def validate_specs(state: ExtrusionState):
    return {'tolerance_check': True}

def check_export_compliance(state: ExtrusionState):
    return {'compliance_cleared': True}

graph = StateGraph(ExtrusionState)
graph.add_node('validate', validate_specs)
graph.add_node('compliance', check_export_compliance)
graph.add_edge('validate', 'compliance')
graph.add_edge('compliance', END)
graph.set_entry_point('validate')
graph = graph.compile()
